from agents import AgentResponse
from orchestration import CustomerServiceOrchestrator


class FakeAgent:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response
        self.exc = exc
        self.calls = []

    def receive_message(self, message):
        self.calls.append(message)
        if self.exc:
            raise self.exc
        if callable(self.response):
            return self.response(message)
        return self.response


def order_response(message):
    order_id = message.data["extracted_data"].get("order_id", "202404250001")
    return AgentResponse(
        True,
        "order ok",
        data={
            "order": {
                "order_id": order_id,
                "shipment": {"tracking_number": "SF1000000001", "status": "in_transit"},
            }
        },
    )


def logistics_response(message):
    return AgentResponse(True, "logistics ok", data={"seen_entities": dict(message.data["extracted_data"])})


def test_orchestrator_inherits_context_for_followup_logistics():
    orchestrator = CustomerServiceOrchestrator()
    orchestrator.agents["order"] = FakeAgent(order_response)
    orchestrator.agents["logistics"] = FakeAgent(logistics_response)

    first = orchestrator.process_message("我想查订单202404250001")
    second = orchestrator.process_message("那物流到哪里了", session_id=first["session_id"])

    assert second["intent"] == "logistics"
    assert second["agent"] == "logistics"
    assert second["data"]["routing"]["context_used"] is True
    assert second["data"]["seen_entities"]["order_id"] == "202404250001"
    assert second["data"]["seen_entities"]["tracking_number"] == "SF1000000001"


def test_orchestrator_order_support_lookup_for_logistics_trace():
    orchestrator = CustomerServiceOrchestrator()
    orchestrator.agents["order"] = FakeAgent(order_response)
    orchestrator.agents["logistics"] = FakeAgent(logistics_response)

    result = orchestrator.process_message("订单202404250001 的物流到哪里了")
    trace_agents = [item["agent"] for item in result["routing_trace"] if item["agent"] != "orchestrator"]

    assert result["agent"] == "logistics"
    assert result["data"]["routing"]["support_agents"] == ["order"]
    assert trace_agents == ["router", "order", "logistics", "quality_safety"]


def test_orchestrator_unknown_returns_clarification_without_business_call():
    orchestrator = CustomerServiceOrchestrator()
    order_agent = FakeAgent(order_response)
    orchestrator.agents["order"] = order_agent

    result = orchestrator.process_message("你好")

    assert result["success"] is False
    assert result["intent"] == "unknown"
    assert result["agent"] == "router"
    assert result["data"]["need_info"] == ["order_id", "tracking_number", "intent"]
    assert order_agent.calls == []


def test_orchestrator_agent_exception_is_controlled_escalation():
    orchestrator = CustomerServiceOrchestrator()
    orchestrator.agents["refund"] = FakeAgent(exc=RuntimeError("refund agent down"))

    result = orchestrator.process_message("订单202404250001 我要退款，质量有问题")

    assert result["success"] is False
    assert result["agent"] == "refund"
    assert result["need_escalate"] is True
    assert result["escalate_reason"] == "agent_runtime_error"
    assert result["data"]["error"] == "refund agent down"
    assert any(item.get("error") == "refund agent down" for item in result["routing_trace"])
