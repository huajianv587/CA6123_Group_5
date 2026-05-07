from quality_safety.evaluation import SessionJudge


def test_session_judge_classifies_unresolved_unsatisfied_session():
    result = SessionJudge().evaluate(
        {
            "session_id": "s1",
            "messages": [{"role": "assistant", "success": False, "need_escalate": True}],
            "traces": [{"router_emotion_score": 2}, {"router_emotion_score": 8}],
        }
    )

    assert result["resolved"] is False
    assert result["satisfied"] is False
    assert result["emotion_trend"] == "恶化"
    assert result["recommended_action"] == "human_followup"
