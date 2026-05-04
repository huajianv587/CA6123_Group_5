from agents.base_agent import IntentType, Message
from orchestration.router import RouterAgent


class DummyLLM:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0

    def classify_intent(self, text: str):
        self.calls += 1
        return self.result


def route(text: str, llm=None):
    msg = Message("user", "router", IntentType.UNKNOWN, text)
    return RouterAgent(llm=llm).receive_message(msg)


def classify(text: str) -> str:
    return route(text).data["intent"]


def test_router_intents_with_real_chinese():
    assert classify("我想查订单202404250001") == "order"
    assert classify("SF1000000001 到哪了") == "logistics"
    assert classify("订单202404250002 我要退款，质量有问题") == "refund"
    assert classify("我要投诉，你们服务太差了") == "complaint"
    assert classify("你好") == "unknown"


def test_router_conflict_priority_and_entities():
    response = route("订单202404250002 我要退款，质量有问题")

    assert response.data["intent"] == "refund"
    assert response.next_agent == "refund"
    assert response.data["extracted_data"]["order_id"] == "202404250002"
    assert response.data["extracted_data"]["refund_reason"] == "quality_issue"
    assert response.data["candidate_intents"][0]["intent"] == "refund"


def test_router_logistics_with_order_id_keeps_entity():
    response = route("订单202404250001 的物流到哪里了")

    assert response.data["intent"] == "logistics"
    assert response.next_agent == "logistics"
    assert response.data["extracted_data"]["order_id"] == "202404250001"


def test_router_high_confidence_rule_does_not_call_llm():
    llm = DummyLLM({"intent": "refund", "confidence": 0.99, "entities": {}})

    response = route("订单202404250001 的物流到哪里了", llm=llm)

    assert response.data["intent"] == "logistics"
    assert llm.calls == 0


def test_router_low_confidence_rule_uses_llm_override():
    llm = DummyLLM({"intent": "logistics", "confidence": 0.8, "entities": {"tracking_number": "SF1000000001"}})

    response = route("帮我看一下这个问题", llm=llm)

    assert llm.calls == 1
    assert response.data["intent"] == "logistics"
    assert response.next_agent == "logistics"
    assert response.data["extracted_data"]["tracking_number"] == "SF1000000001"
    assert response.data["llm_used"] is True
