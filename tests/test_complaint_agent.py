from agents import IntentType, Message
from agents.complaint import ComplaintAgent


def _message(text, session_id="complaint-session"):
    return Message(
        sender="router",
        receiver="complaint",
        intent=IntentType.COMPLAINT,
        content=text,
        data={},
        session_id=session_id,
    )


def test_complaint_agent_uses_scenario_specific_soothing():
    response = ComplaintAgent().receive_message(_message("你们客服一直不回复，没人管"))

    assert response.success is True
    assert "服务响应问题" in response.message
    assert response.data["action"] == "comfort"


def test_complaint_agent_escalates_repeated_same_session_complaints():
    agent = ComplaintAgent()

    agent.receive_message(_message("这个问题还没解决"))
    agent.receive_message(_message("我又来反馈一次"))
    response = agent.receive_message(_message("还是没人处理"))

    assert response.need_escalate is True
    assert "重复投诉" in response.escalate_reason
