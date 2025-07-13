from fastapi import APIRouter, HTTPException, BackgroundTasks

from web_searcher.api.lifespan import session_manager
from web_searcher.models.schemas import SessionResponse, QueryResponse, QueryRequest

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(timeout_minutes: int = 30):
    """Create a new browser session"""
    session = await session_manager.create_session(timeout_minutes)

    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        page_url=session.page.url if session.page else None
    )


@router.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """Close a browser session"""
    success = await session_manager.close_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session closed"}


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session information"""
    session = session_manager.get_session(session_id)

    return SessionResponse(
        session_id=session.session_id,
        status=session.status,
        page_url=session.page.url if session.page else None,
        current_query=session.current_query,
        result=session.result,
        error=session.error
    )


@router.post("/sessions/{session_id}/query", response_model=QueryResponse)
async def query_agent(session_id: str, request: QueryRequest, background_tasks: BackgroundTasks):
    """Execute a query using the web agent"""
    session = session_manager.get_session(session_id)

    # Set session status to processing
    session.status = "processing"
    session.current_query = request.question
    session.result = None
    session.error = None

    async def process_query():
        try:
            event_stream = session.graph.astream(
                {
                    "page": session.page,
                    "input": request.question,
                    "scratchpad": [],
                },
                {"recursion_limit": request.max_steps},
            )

            final_answer = None
            step_count = 0

            async for event in event_stream:
                if "agent" not in event:
                    continue

                step_count += 1
                pred = event["agent"].get("prediction") or {}
                action = pred.get("action")
                action_input = pred.get("args")

                # Update session with current step info
                session.current_step = step_count
                session.current_action = f"{action}: {action_input}"

                if "ANSWER" in action:
                    final_answer = action_input[0] if action_input else None
                    break

                if step_count > request.max_steps:
                    raise Exception(f"Max steps ({request.max_steps}) exceeded")

            session.status = "completed"
            session.result = final_answer

        except Exception as e:
            session.status = "error"
            session.error = str(e)
            print(f" [ERROR] Query error in session {session_id}: {e}")

    background_tasks.add_task(process_query)

    return QueryResponse(
        session_id=session_id,
        status="processing",
        answer=None
    )


# Additional monitoring endpoints
@router.get("/sessions")
async def list_sessions():
    """List all active sessions (for monitoring)"""
    return {
        "active_sessions": session_manager.get_session_count(),
        "sessions": session_manager.get_session_info()
    }
