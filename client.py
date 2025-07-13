import asyncio
import httpx
import time
from typing import Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebAgentClient:
    """Client for interacting with WebVoyager API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
        self.session_id: Optional[str] = None

    async def create_session(self, timeout_minutes: int = 30) -> str:
        """Create a new browser session"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/sessions",
                    params={"timeout_minutes": timeout_minutes}
                )
                response.raise_for_status()

                session_data = response.json()
                self.session_id = session_data["session_id"]
                logger.info(f"Created session: {self.session_id}")
                return self.session_id

            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to create session: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error creating session: {e}")
                raise

    async def get_session_info(self) -> Dict[str, Any]:
        """Get current session information"""
        if not self.session_id:
            raise ValueError("No active session")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/sessions/{self.session_id}")
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning("Session not found or expired")
                    self.session_id = None
                raise
            except Exception as e:
                logger.error(f"Error getting session info: {e}")
                raise

    async def query_async(self, question: str, max_steps: int = 150, poll_interval: int = 2) -> Optional[str]:
        """Execute a query asynchronously with polling"""
        if not self.session_id:
            raise ValueError("No active session")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Start the query
                query_data = {
                    "question": question,
                    "max_steps": max_steps
                }

                response = await client.post(
                    f"{self.base_url}/sessions/{self.session_id}/query",
                    json=query_data
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"Query started: {result['status']}")

                # Poll for completion
                start_time = time.time()
                while True:
                    session_info = await self.get_session_info()
                    status = session_info['status']

                    # Log progress if available
                    if 'current_step' in session_info and session_info['current_step']:
                        logger.info(
                            f"Step {session_info['current_step']}: {session_info.get('current_action', 'Processing...')}")

                    if status == 'completed':
                        answer = session_info.get('result')
                        elapsed = time.time() - start_time
                        logger.info(f"Query completed in {elapsed:.2f}s")
                        return answer

                    elif status == 'error':
                        error = session_info.get('error', 'Unknown error')
                        logger.error(f"Query failed: {error}")
                        raise Exception(f"Query failed: {error}")

                    elif status == 'processing':
                        logger.info(f"Status: {status}")

                    # Wait before polling again
                    await asyncio.sleep(poll_interval)

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error during async query: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error during async query: {e}")
                raise

    async def close_session(self) -> bool:
        """Close the current session"""
        if not self.session_id:
            return False

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.delete(f"{self.base_url}/sessions/{self.session_id}")
                response.raise_for_status()

                logger.info(f"Session {self.session_id} closed")
                self.session_id = None
                return True

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning("Session not found (may have already expired)")
                    self.session_id = None
                    return True
                logger.error(f"Error closing session: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Error closing session: {e}")
                raise

    async def list_sessions(self) -> Dict[str, Any]:
        """List all active sessions (for monitoring)"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/sessions")
                response.raise_for_status()
                return response.json()

            except Exception as e:
                logger.error(f"Error listing sessions: {e}")
                raise

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - automatically close session"""
        if self.session_id:
            try:
                await self.close_session()
            except Exception as e:
                logger.error(f"Error closing session in context manager: {e}")


async def main():
    """Example usage of the improved client"""
    # Use context manager for automatic session cleanup
    async with WebAgentClient() as client:
        try:
            # Create session with custom timeout
            session_id = await client.create_session(timeout_minutes=45)

            # Get initial session info
            session_info = await client.get_session_info()
            print(f"Session created: {session_id}")
            print(f"Initial page: {session_info.get('page_url')}")

            print("\n=== Using Async Query ===")
            try:
                answer = await client.query_async(
                    question="What's the weather in Paris?",
                    max_steps=40,
                    poll_interval=3  # Poll every 3 seconds
                )
                print(f"Answer: {answer}")

            except Exception as e:
                logger.error(f"Async query failed: {e}")

            # Get final session info
            final_info = await client.get_session_info()
            print(f"\nFinal page: {final_info.get('page_url')}")

        except Exception as e:
            logger.error(f"Main execution error: {e}")

    # Context automatically closes session manager
    print("\nSession automatically closed")


if __name__ == "__main__":
    asyncio.run(main())
