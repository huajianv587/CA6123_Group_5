from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    message: str


class ChatResponse(BaseModel):
    success: bool
    session_id: str
    response: str
    intent: str
    agent: str
    need_escalate: bool
    escalate_reason: str
    data: dict[str, Any]
    rag_used: bool
    rag_sources: list[str]
    routing_trace: list[dict[str, Any]] = Field(default_factory=list)
    router_confidence: Optional[float] = None
    candidate_intents: list[dict[str, Any]] = Field(default_factory=list)


class ResolveRequest(BaseModel):
    note: Optional[str] = None
