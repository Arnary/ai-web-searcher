import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from uuid import uuid4
from fastapi import HTTPException
import logging
from threading import RLock
from datetime import datetime, timedelta

from web_searcher.agents.graph import create_agent_graph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Structured session information"""
    session_id: str
    page: Any  # Playwright Page object
    graph: Any  # LangGraph object
    status: str = "active"
    current_query: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    current_step: Optional[int] = None
    current_action: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    timeout_minutes: int = 30  # Default session timeout

    def update_last_accessed(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.now()

    def is_expired(self) -> bool:
        """Check if the session has expired"""
        return datetime.now() - self.last_accessed > timedelta(minutes=self.timeout_minutes)


class SessionManager:
    """Thread-safe session manager with automatic cleanup"""

    def __init__(self, cleanup_interval: int = 300):  # 5 minutes
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = RLock()
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._browser = None

    async def initialize(self, browser):
        """Initialize the session manager with browser instance"""
        self._browser = browser
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())

    async def create_session(self, timeout_minutes: int = 30) -> SessionInfo:
        """Create a new browser session"""
        if not self._browser:
            raise RuntimeError("Browser not initialized")

        session_id = str(uuid4())

        try:
            page = await self._browser.new_page()
            await page.goto("https://www.duckduckgo.com")

            session = SessionInfo(
                session_id=session_id,
                page=page,
                graph=create_agent_graph(),
                timeout_minutes=timeout_minutes
            )

            with self._lock:
                self._sessions[session_id] = session

            logger.info(f"Created session {session_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")

    def get_session(self, session_id: str) -> SessionInfo:
        """Get session by ID and update last accessed time"""
        with self._lock:
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            session = self._sessions[session_id]

            # Check if the session is expired
            if session.is_expired():
                # Clean up expired session
                asyncio.create_task(self._cleanup_session(session_id))
                raise HTTPException(status_code=404, detail="Session expired")

            session.update_last_accessed()
            return session

    async def close_session(self, session_id: str) -> bool:
        """Close a specific session"""
        with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]

        # Close page outside lock to avoid blocking
        try:
            if session.page:
                await session.page.close()
        except Exception as e:
            logger.warning(f"Error closing page for session {session_id}: {e}")

        with self._lock:
            del self._sessions[session_id]

        logger.info(f"Closed session {session_id}")
        return True

    async def _cleanup_session(self, session_id: str):
        """Internal method to clean up a single session"""
        try:
            await self.close_session(session_id)
        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")

    async def _cleanup_expired_sessions(self):
        """Background task to clean up expired sessions"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)

                expired_sessions = []
                with self._lock:
                    for session_id, session in self._sessions.items():
                        if session.is_expired():
                            expired_sessions.append(session_id)

                # Clean up expired sessions
                for session_id in expired_sessions:
                    logger.info(f"Cleaning up expired session {session_id}")
                    await self._cleanup_session(session_id)

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def close_all_sessions(self):
        """Close all sessions (for shutdown)"""
        session_ids = list(self._sessions.keys())

        # Close all sessions concurrently
        tasks = [self.close_session(session_id) for session_id in session_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def get_session_count(self) -> int:
        """Get the current number of active sessions"""
        with self._lock:
            return len(self._sessions)

    def get_session_info(self) -> Dict[str, Dict[str, Any]]:
        """Get info about all sessions (for debugging/monitoring)"""
        with self._lock:
            return {
                session_id: {
                    "status": session.status,
                    "created_at": session.created_at.isoformat(),
                    "last_accessed": session.last_accessed.isoformat(),
                    "current_query": session.current_query,
                    "page_url": session.page.url if session.page else None
                }
                for session_id, session in self._sessions.items()
            }
