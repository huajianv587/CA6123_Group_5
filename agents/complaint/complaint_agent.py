from agents.base_agent import AgentResponse, BaseAgent, Message


class ComplaintAgent(BaseAgent):
    def __init__(self, store=None, **kwargs):
        super().__init__("complaint", "ComplaintAgent", store=store, **kwargs)
        self.weights = {
            "angry": (["生气", "愤怒", "垃圾", "太差", "离谱", "恶心"], 2.0),
            "threat": (["投诉", "12315", "曝光", "律师", "法院", "媒体"], 2.8),
            "human": (["人工", "经理", "主管", "负责人", "真人"], 2.0),
            "urgent": (["马上", "立刻", "现在", "赶紧"], 1.5),
        }

    def process(self, message: Message) -> AgentResponse:
        emotion = self._emotion(message.content, message.data.get("emotion_level", {}))
        needs_escalation, reason = self._needs_escalation(emotion)
        user_id = message.data.get("user_id")
        if self.store:
            self.store.create_complaint(
                session_id=message.session_id,
                user_id=user_id,
                content=message.content,
                emotion_level=emotion["level"],
                emotion_score=emotion["total_score"],
                escalation_reason=reason if needs_escalation else None,
                status="open" if needs_escalation else "handled",
            )
        if needs_escalation:
            return AgentResponse(
                True,
                f"已为您升级人工客服。\n升级原因：{reason}\n当前会优先处理您的问题，请保持联系方式畅通。",
                data={"emotion_analysis": emotion, "action": "escalate"},
                need_escalate=True,
                escalate_reason=reason,
            )
        return AgentResponse(True, self._comfort(message.content, emotion), data={"emotion_analysis": emotion, "action": "comfort"})

    def _emotion(self, text: str, router_emotion: dict) -> dict:
        scores = {}
        total = 0.0
        for key, (keywords, weight) in self.weights.items():
            score = sum(text.count(k) for k in keywords) * weight
            scores[key] = score
            total += score
        router_score = router_emotion.get("total_score", 0) if isinstance(router_emotion, dict) else 0
        total = max(total, float(router_score or 0))
        level = "high" if total >= 6 else "medium" if total >= 2.5 else "low"
        return {"level": level, "total_score": total, "scores": scores}

    def _needs_escalation(self, emotion: dict) -> tuple[bool, str]:
        reasons = []
        if emotion["total_score"] >= 6:
            reasons.append("情绪强烈")
        if emotion["scores"].get("threat", 0) >= 2.8:
            reasons.append("涉及投诉/曝光/法律风险")
        if emotion["scores"].get("human", 0) >= 2:
            reasons.append("用户明确要求人工")
        return bool(reasons), "；".join(reasons)

    def _comfort(self, text: str, emotion: dict) -> str:
        prefix = "非常抱歉给您带来不好的体验。"
        if emotion["level"] == "medium":
            prefix = "理解您的不满，我会优先帮您核实并推进处理。"
        solution = "请补充订单号、问题照片或物流单号，我会继续为您处理。"
        if any(k in text for k in ["质量", "坏", "破损"]):
            solution = "如涉及质量问题，我们可以协助您发起退款、换货或补偿审核。"
        if any(k in text for k in ["没到", "延迟", "没收到"]):
            solution = "我会建议先核查物流轨迹和签收信息，必要时升级人工调查。"
        return f"{prefix}\n{solution}"
