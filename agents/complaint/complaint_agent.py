from agents.base_agent import AgentResponse, BaseAgent, Message


SOOTHE_TEMPLATES = {
    "anger": [
        "非常抱歉给您带来了不好的体验，我完全理解您现在的心情。",
        "您的感受完全可以理解，我们有责任为您解决这个问题。",
    ],
    "threat": [
        "您的诉求我已经认真记录，会第一时间为您跟进处理。",
        "您有权通过正规渠道维权，同时我也会尽力在这里推进问题解决。",
    ],
    "agitation": [
        "非常抱歉让您有这样的感受，请告诉我具体发生了什么。",
        "我能感受到您的失望，我会认真对待您的诉求。",
    ],
    "general": [
        "感谢您联系我们，我会尽力帮助您解决问题。",
        "我理解您的情况，让我来帮您处理。",
    ],
}


SCENARIO_TEMPLATES = [
    (
        ["没到", "慢", "等太久", "延迟", "还没收到", "什么时候到"],
        "关于配送延迟，我会协助您核查物流状态；如确认超出承诺时效，可继续申请补偿、补发或人工核查。",
    ),
    (
        ["质量", "坏", "破", "瑕疵", "故障", "损坏", "有问题"],
        "如涉及质量问题，我们可以协助您发起退款、换货或补偿审核，请补充订单号和问题照片。",
    ),
    (
        ["态度", "客服", "不理", "不回复", "没人管", "联系不上"],
        "对于服务响应问题我会记录并反馈，同时继续跟进当前问题直到有明确处理结果。",
    ),
    (
        ["发错", "不对", "少发", "漏发", "错发", "不是我要的"],
        "如果存在错发、漏发或商品不符，我们可以协助核实并发起补发、退换货或赔付流程。",
    ),
    (
        ["退款没到", "退款慢", "退款多久", "还没退"],
        "退款到账通常需要 3-7 个工作日，具体取决于支付方式；请提供订单号，我可以帮您核查进度。",
    ),
]


class ComplaintAgent(BaseAgent):
    def __init__(self, store=None, **kwargs):
        super().__init__("complaint", "ComplaintAgent", store=store, **kwargs)
        self.weights = {
            "angry": (["生气", "愤怒", "垃圾", "太差", "离谱", "恶心", "气死", "骗子", "欺诈"], 2.0),
            "threat": (["投诉", "12315", "曝光", "律师", "法院", "媒体", "起诉", "报警", "仲裁"], 2.8),
            "human": (["人工", "经理", "主管", "负责人", "真人"], 2.0),
            "urgent": (["马上", "立刻", "现在", "赶紧", "必须", "否则", "不然"], 1.5),
        }
        self._complaint_counts: dict[str, int] = {}

    def process(self, message: Message) -> AgentResponse:
        emotion = self._emotion(message.content, message.data.get("emotion_level", {}))
        complaint_count = self._increment_complaint_count(message.session_id or "default")
        needs_escalation, reason = self._needs_escalation(emotion, complaint_count)
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
        return AgentResponse(
            True,
            self._comfort(message.content, emotion, complaint_count),
            data={"emotion_analysis": emotion, "complaint_count": complaint_count, "action": "comfort"},
        )

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

    def _needs_escalation(self, emotion: dict, complaint_count: int) -> tuple[bool, str]:
        reasons = []
        if emotion["total_score"] >= 6:
            reasons.append("情绪强烈")
        if emotion["scores"].get("threat", 0) >= 2.8:
            reasons.append("涉及投诉/曝光/法律风险")
        if emotion["scores"].get("human", 0) >= 2:
            reasons.append("用户明确要求人工")
        if complaint_count >= 3:
            reasons.append("同一会话重复投诉")
        return bool(reasons), "；".join(reasons)

    def _comfort(self, text: str, emotion: dict, complaint_count: int) -> str:
        template_key = "general"
        if emotion["scores"].get("threat", 0) >= 2.8:
            template_key = "threat"
        elif emotion["scores"].get("angry", 0) >= 2:
            template_key = "anger"
        elif emotion["level"] == "medium":
            template_key = "agitation"

        opener = SOOTHE_TEMPLATES[template_key][min(complaint_count - 1, len(SOOTHE_TEMPLATES[template_key]) - 1)]
        scenario = "请补充订单号、问题照片或物流单号，我会继续为您处理。"
        for keywords, response in SCENARIO_TEMPLATES:
            if any(keyword in text for keyword in keywords):
                scenario = response
                break

        repeat_note = ""
        if complaint_count >= 2:
            repeat_note = "\n我注意到您已经多次反馈，非常抱歉还没有解决，我会重点跟进。"
        return f"{opener}\n{scenario}{repeat_note}"

    def _increment_complaint_count(self, session_id: str) -> int:
        self._complaint_counts[session_id] = self._complaint_counts.get(session_id, 0) + 1
        return self._complaint_counts[session_id]
