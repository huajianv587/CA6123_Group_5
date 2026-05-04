import uuid
from typing import Any, Optional

from agents import AgentResponse, ComplaintAgent, IntentType, LogisticsAgent, Message, OrderAgent, RefundAgent
from integrations import OpenAIClient
from knowledge import KnowledgeRetriever
from orchestration.router import RouterAgent
from quality_safety import QualitySafetyAgent


class CustomerServiceOrchestrator:
    def __init__(self, store=None, build_index_on_start: bool = False):
        self.store = store
        self.llm = OpenAIClient()
        self.retriever = KnowledgeRetriever(store=store, llm=self.llm)
        self.safety = QualitySafetyAgent()
        self.router = RouterAgent(llm=self.llm, store=store)
        self.agents = {
            "order": OrderAgent(store=store),
            "logistics": LogisticsAgent(store=store),
            "refund": RefundAgent(store=store, retriever=self.retriever),
            "complaint": ComplaintAgent(store=store),
        }
        self.sessions: dict[str, dict] = {}
        self.stats = {
            "total_requests": 0,
            "escalation_count": 0,
            "intent_distribution": {i.value: 0 for i in IntentType},
            "rag_hits": 0,
            "rag_sources": {},
        }
        if build_index_on_start:
            self.retriever.build_index()

    def process_message(self, user_input: str, session_id: Optional[str] = None, user_id: Optional[int] = None) -> dict:
        session_id = session_id or self._create_session()
        context = self._load_context(session_id)
        self._record_user_message(session_id, user_input, user_id)

        self.stats["total_requests"] += 1
        router_msg = Message(
            "user",
            "router",
            IntentType.UNKNOWN,
            user_input,
            {"user_id": user_id, "context": context},
            session_id=session_id,
        )
        router_resp = self.router.receive_message(router_msg)
        route_data = dict(router_resp.data)
        intent = route_data.get("intent", "unknown")
        route_data, context_used, inherited_keys = self._apply_context(route_data, context)
        if intent in self.stats["intent_distribution"]:
            self.stats["intent_distribution"][intent] += 1

        trace = [
            {
                "step": "router",
                "agent": "router",
                "intent": intent,
                "confidence": route_data.get("confidence"),
                "next_agent": router_resp.next_agent,
                "reason": route_data.get("route_reason"),
                "entities": route_data.get("extracted_data", {}),
            }
        ]
        support_agents: list[str] = []
        fallback_used = False
        target_id = router_resp.next_agent or "router"

        if intent == IntentType.UNKNOWN.value:
            biz_resp = self._clarify_unknown(route_data)
            trace.append({"step": "clarification", "agent": "router", "success": True})
            target_id = "router"
        else:
            biz_resp, target_id, support_agents, fallback_used = self._dispatch(
                target_id=target_id,
                intent=intent,
                user_input=user_input,
                route_data=route_data,
                session_id=session_id,
                user_id=user_id,
                trace=trace,
            )

        safety = self.safety.review(
            biz_resp.message,
            {"need_escalate": biz_resp.need_escalate, "escalate_reason": biz_resp.escalate_reason},
        )
        biz_resp.message = safety.text
        if safety.need_escalate:
            biz_resp.need_escalate = True
            biz_resp.escalate_reason = biz_resp.escalate_reason or safety.reason
        trace.append(
            {
                "step": "safety",
                "agent": "quality_safety",
                "need_escalate": biz_resp.need_escalate,
                "reason": biz_resp.escalate_reason,
            }
        )

        routing = {
            "context_used": context_used,
            "inherited_keys": inherited_keys,
            "support_agents": support_agents,
            "final_agent": target_id,
            "fallback_used": fallback_used,
        }
        biz_resp.data = {**biz_resp.data, "routing": routing}

        self._record_stats(biz_resp)
        self._record_assistant_message(
            session_id=session_id,
            user_id=user_id,
            target_id=target_id,
            intent=intent,
            response=biz_resp,
            router_data=route_data,
            routing_trace=trace,
        )

        return {
            "success": biz_resp.success,
            "session_id": session_id,
            "response": biz_resp.message,
            "intent": intent,
            "agent": target_id,
            "need_escalate": biz_resp.need_escalate,
            "escalate_reason": biz_resp.escalate_reason,
            "data": biz_resp.data,
            "rag_used": biz_resp.rag_used,
            "rag_sources": biz_resp.rag_sources,
            "routing_trace": trace,
            "router_confidence": route_data.get("confidence"),
            "candidate_intents": route_data.get("candidate_intents", []),
        }

    def _dispatch(
        self,
        target_id: str,
        intent: str,
        user_input: str,
        route_data: dict[str, Any],
        session_id: str,
        user_id: Optional[int],
        trace: list[dict[str, Any]],
    ) -> tuple[AgentResponse, str, list[str], bool]:
        support_agents: list[str] = []
        fallback_used = False
        entities = route_data.setdefault("extracted_data", {})

        if target_id == "logistics" and entities.get("order_id") and not entities.get("tracking_number"):
            support_agents.append("order")
            order_resp = self._call_agent(
                agent_id="order",
                intent=IntentType.ORDER.value,
                content=user_input,
                data=route_data,
                session_id=session_id,
                user_id=user_id,
                trace=trace,
                step="support_order_lookup",
            )
            tracking_number = self._tracking_from_order_response(order_resp)
            if tracking_number:
                entities["tracking_number"] = tracking_number
                trace.append(
                    {
                        "step": "support_data_merge",
                        "agent": "orchestrator",
                        "field": "tracking_number",
                        "source_agent": "order",
                    }
                )
            elif not order_resp.success:
                fallback_used = True
                return order_resp, "order", support_agents, fallback_used

        biz_resp = self._call_agent(
            agent_id=target_id,
            intent=intent,
            content=user_input,
            data=route_data,
            session_id=session_id,
            user_id=user_id,
            trace=trace,
            step="business_agent",
        )
        return biz_resp, target_id, support_agents, fallback_used

    def _call_agent(
        self,
        agent_id: str,
        intent: str,
        content: str,
        data: dict[str, Any],
        session_id: str,
        user_id: Optional[int],
        trace: list[dict[str, Any]],
        step: str,
    ) -> AgentResponse:
        target = self.agents.get(agent_id)
        if target is None:
            trace.append({"step": step, "agent": agent_id, "success": False, "error": "agent_not_registered"})
            return AgentResponse(
                False,
                f"暂时无法找到 {agent_id} 处理模块，已为您转人工处理。",
                data={"error": "agent_not_registered", "agent": agent_id},
                need_escalate=True,
                escalate_reason="agent_not_registered",
            )

        message = Message(
            "router",
            agent_id,
            IntentType(intent) if intent in IntentType._value2member_map_ else IntentType.UNKNOWN,
            content,
            {**data, "user_id": user_id},
            session_id=session_id,
        )
        try:
            response = target.receive_message(message)
            trace.append({"step": step, "agent": agent_id, "success": response.success})
            return response
        except Exception as exc:
            trace.append({"step": step, "agent": agent_id, "success": False, "error": str(exc)})
            return AgentResponse(
                False,
                "系统在调用业务处理模块时出现异常，已为您转人工处理。",
                data={"error": str(exc), "agent": agent_id},
                need_escalate=True,
                escalate_reason="agent_runtime_error",
            )

    def _clarify_unknown(self, route_data: dict[str, Any]) -> AgentResponse:
        return AgentResponse(
            False,
            "我还需要更多信息才能处理。请补充订单号、物流单号，或说明您要查询订单、物流、退款还是投诉。",
            data={
                "need_info": ["order_id", "tracking_number", "intent"],
                "extracted_data": route_data.get("extracted_data", {}),
                "action": "clarify",
            },
        )

    def _tracking_from_order_response(self, response: AgentResponse) -> Optional[str]:
        order = response.data.get("order") if response and response.data else None
        shipment = order.get("shipment") if isinstance(order, dict) else None
        tracking_number = shipment.get("tracking_number") if isinstance(shipment, dict) else None
        return tracking_number or None

    def _record_user_message(self, session_id: str, user_input: str, user_id: Optional[int]) -> None:
        if self.store:
            self.store.get_or_create_session(session_id, user_id=user_id)
            self.store.add_message(session_id=session_id, role="user", content=user_input, metadata={"user_id": user_id})
        else:
            self.sessions.setdefault(session_id, {"messages": [], "status": "active"})
            self.sessions[session_id]["messages"].append(
                {"role": "user", "content": user_input, "metadata": {"user_id": user_id}}
            )

    def _record_assistant_message(
        self,
        session_id: str,
        user_id: Optional[int],
        target_id: str,
        intent: str,
        response: AgentResponse,
        router_data: dict[str, Any],
        routing_trace: list[dict[str, Any]],
    ) -> None:
        metadata = {
            "data": response.data,
            "need_escalate": response.need_escalate,
            "router": router_data,
            "routing_trace": routing_trace,
        }
        if self.store:
            session = self.store.get_or_create_session(session_id, user_id=user_id)
            session.escalated = bool(response.need_escalate)
            session.status = "escalated" if response.need_escalate else "active"
            self.store.add_message(
                session_id=session_id,
                role="assistant",
                content=response.message,
                agent=target_id,
                intent=intent,
                rag_sources=response.rag_sources,
                metadata=metadata,
            )
        else:
            self.sessions[session_id]["messages"].append(
                {
                    "role": "assistant",
                    "content": response.message,
                    "agent": target_id,
                    "intent": intent,
                    "rag_sources": response.rag_sources,
                    "metadata": metadata,
                }
            )

    def _record_stats(self, response: AgentResponse) -> None:
        if response.rag_used:
            self.stats["rag_hits"] += 1
            for src in response.rag_sources:
                self.stats["rag_sources"][src] = self.stats["rag_sources"].get(src, 0) + 1
        if response.need_escalate:
            self.stats["escalation_count"] += 1

    def _load_context(self, session_id: str) -> dict[str, Any]:
        context = {"last_intent": None, "last_agent": None, "last_entities": {}}
        messages = self._session_messages(session_id)
        for message in reversed(messages):
            metadata = self._message_metadata(message)
            router_data = metadata.get("router") or {}
            entities = dict(router_data.get("extracted_data") or {})
            if not entities:
                entities = self._entities_from_response_data((metadata.get("data") or {}))
            if entities or self._message_intent(message):
                context["last_intent"] = self._message_intent(message)
                context["last_agent"] = self._message_agent(message)
                context["last_entities"] = entities
                return context
        return context

    def _session_messages(self, session_id: str) -> list[Any]:
        if self.store:
            return self.store.get_session_messages(session_id)
        return self.sessions.get(session_id, {}).get("messages", [])

    def _message_metadata(self, message: Any) -> dict[str, Any]:
        if isinstance(message, dict):
            return message.get("metadata") or {}
        return getattr(message, "metadata_json", None) or {}

    def _message_intent(self, message: Any) -> Optional[str]:
        if isinstance(message, dict):
            return message.get("intent")
        return getattr(message, "intent", None)

    def _message_agent(self, message: Any) -> Optional[str]:
        if isinstance(message, dict):
            return message.get("agent")
        return getattr(message, "agent", None)

    def _entities_from_response_data(self, data: dict[str, Any]) -> dict[str, Any]:
        entities: dict[str, Any] = {}
        order = data.get("order") if isinstance(data, dict) else None
        if isinstance(order, dict):
            if order.get("order_id"):
                entities["order_id"] = order["order_id"]
            shipment = order.get("shipment")
            if isinstance(shipment, dict) and shipment.get("tracking_number"):
                entities["tracking_number"] = shipment["tracking_number"]

        tracking = data.get("tracking") if isinstance(data, dict) else None
        if isinstance(tracking, dict) and tracking.get("tracking_number"):
            entities["tracking_number"] = tracking["tracking_number"]
        extracted = data.get("extracted_data") if isinstance(data, dict) else None
        if isinstance(extracted, dict):
            entities.update(extracted)
        return entities

    def _apply_context(self, route_data: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], bool, list[str]]:
        current = dict(route_data.get("extracted_data") or {})
        previous = dict(context.get("last_entities") or {})
        inherited_keys: list[str] = []
        for key in ["order_id", "tracking_number", "phone", "refund_reason"]:
            if key not in current and previous.get(key):
                current[key] = previous[key]
                inherited_keys.append(key)
        route_data["extracted_data"] = current
        return route_data, bool(inherited_keys), inherited_keys

    def get_stats(self) -> dict:
        if self.store:
            db_metrics = self.store.metrics()
        else:
            db_metrics = {"total_sessions": len(self.sessions)}
        total = self.stats["total_requests"]
        return {
            **self.stats,
            **db_metrics,
            "rag_hit_rate_memory": f"{(self.stats['rag_hits'] / total * 100) if total else 0:.1f}%",
            "retriever_stats": self.retriever.get_stats(),
        }

    def _create_session(self) -> str:
        return str(uuid.uuid4())[:8]


_orchestrator: Optional[CustomerServiceOrchestrator] = None


def get_orchestrator(build_index_on_start: bool = False) -> CustomerServiceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CustomerServiceOrchestrator(build_index_on_start=build_index_on_start)
    return _orchestrator
