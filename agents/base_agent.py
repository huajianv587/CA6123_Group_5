import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class IntentType(Enum):
    ORDER = "order"
    LOGISTICS = "logistics"
    REFUND = "refund"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


@dataclass
class Message:
    sender: str
    receiver: str
    intent: IntentType
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "intent": self.intent.value,
            "content": self.content,
            "data": self.data,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
        }


@dataclass
class AgentResponse:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    need_escalate: bool = False
    escalate_reason: str = ""
    next_agent: Optional[str] = None
    rag_used: bool = False
    rag_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "need_escalate": self.need_escalate,
            "escalate_reason": self.escalate_reason,
            "next_agent": self.next_agent,
            "rag_used": self.rag_used,
            "rag_sources": self.rag_sources,
        }


class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str, retriever=None, store=None, llm=None, guardrail=None):
        self.agent_id = agent_id
        self.name = name
        self._retriever = retriever
        self.store = store
        self.llm = llm
        self.guardrail = guardrail
        self._guardrail = guardrail
        self.message_history: list[Message] = []

    @abstractmethod
    def process(self, message: Message) -> AgentResponse:
        raise NotImplementedError

    def receive_message(self, message: Message) -> AgentResponse:
        self.message_history.append(message)
        started = time.perf_counter()
        try:
            response = self.process(message)
            self._record_event(message, response.success, started, None)
            return response
        except Exception as exc:
            self._record_event(message, False, started, str(exc))
            raise

    def retrieve_knowledge(self, query: str, top_k: int = 3, category_filter: Optional[str] = None):
        if self._retriever is None:
            return []
        return self._retriever.retrieve(query=query, top_k=top_k, category=category_filter)

    def format_rag_context(self, results, max_chars: int = 800) -> str:
        if self._retriever is None:
            return ""
        return self._retriever.format_context(results, max_chars=max_chars)

    def _record_event(self, message: Message, success: bool, started: float, error: Optional[str]) -> None:
        if not self.store:
            return
        duration_ms = (time.perf_counter() - started) * 1000
        self.store.add_agent_event(
            agent=self.agent_id,
            success=success,
            duration_ms=duration_ms,
            session_id=message.session_id,
            intent=message.intent.value,
            error=error,
        )

    def log(self, text: str) -> None:
        print(f"[{self.name}] {text}")
