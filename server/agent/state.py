from typing import TypedDict, List, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


class WorkflowState(TypedDict, total=False):
    """State for the AI 研发效能 Agent workflow (Phase 6+)."""
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    task_id: str
    intent: str
    intent_confidence: float
    intent_reason: str
    retrieved_context: list
    tool_results: dict
    citations: list
    final_answer: str
    latency_ms: int
    success: bool
    requires_confirmation: bool
