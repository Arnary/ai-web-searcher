from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from playwright.async_api import Page


class BBox(TypedDict):
    x: float
    y: float
    text: str
    type: str
    ariaLabel: str


class Prediction(TypedDict):
    action: str
    args: Optional[List[str]]


class AgentState(TypedDict):
    page: Page
    input: str
    img: str
    bboxes: List[BBox]
    prediction: Prediction
    scratchpad: List[BaseMessage]
    observation: str


class QueryRequest(BaseModel):
    question: str = Field(..., description="The question to ask the web agent")
    max_steps: int = Field(default=150, description="Maximum number of steps to execute")


class QueryResponse(BaseModel):
    session_id: str
    status: Literal["processing", "completed", "error"]
    answer: Optional[str] = None
    error: Optional[str] = None
    current_step: Optional[int] = None
    current_action: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    status: Literal["active", "processing", "completed", "error"]
    page_url: Optional[str] = None
    current_query: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
