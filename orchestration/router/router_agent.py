import re
from typing import Any

from agents.base_agent import AgentResponse, BaseAgent, IntentType, Message


class RouterAgent(BaseAgent):
    LOW_CONFIDENCE_THRESHOLD = 0.5
    AMBIGUITY_DELTA = 0.15
    LLM_OVERRIDE_THRESHOLD = 0.72

    def __init__(self, llm=None, store=None):
        super().__init__("router", "RouterAgent", llm=llm, store=store)
        self.keyword_map = {
            IntentType.ORDER: [
                "订单",
                "下单",
                "购买",
                "商品",
                "地址",
                "取消",
                "订单号",
                "改地址",
                "修改地址",
                "查订单",
                "我的订单",
                "最近订单",
                "全部订单",
            ],
            IntentType.LOGISTICS: [
                "物流",
                "快递",
                "发货",
                "配送",
                "签收",
                "运单",
                "到哪",
                "到哪里",
                "没收到",
                "没有收到",
                "派送",
                "运输",
                "包裹",
                "轨迹",
                "查物流",
            ],
            IntentType.REFUND: [
                "退款",
                "退货",
                "退钱",
                "售后",
                "七天",
                "质量",
                "坏了",
                "不想要",
                "不喜欢",
                "有问题",
                "破损",
                "故障",
                "换货",
                "赔付",
            ],
            IntentType.COMPLAINT: [
                "投诉",
                "差评",
                "生气",
                "愤怒",
                "经理",
                "人工",
                "12315",
                "曝光",
                "服务态度",
                "太差",
                "律师",
                "法院",
                "媒体",
                "主管",
                "负责人",
                "真人",
            ],
        }
        self.priority = {
            IntentType.COMPLAINT: 4,
            IntentType.REFUND: 3,
            IntentType.LOGISTICS: 2,
            IntentType.ORDER: 1,
            IntentType.UNKNOWN: 0,
        }

    def process(self, message: Message) -> AgentResponse:
        rule_result = self._classify_by_rules(message.content)
        intent = rule_result["intent"]
        confidence = rule_result["confidence"]
        entities = dict(rule_result["extracted_data"])
        emotion = rule_result["emotion_level"]
        route_reason = rule_result["route_reason"]
        llm_used = False

        if self._should_try_llm(rule_result):
            llm_result = self.llm.classify_intent(message.content) if self.llm else None
            if llm_result:
                llm_used = True
                llm_intent = self._intent_from_text(llm_result.get("intent", "unknown"))
                llm_confidence = float(llm_result.get("confidence", 0) or 0)
                llm_entities = llm_result.get("entities") or {}
                if llm_confidence >= self.LLM_OVERRIDE_THRESHOLD:
                    intent = llm_intent
                    confidence = llm_confidence
                    entities = {**entities, **llm_entities}
                    emotion = llm_result.get("emotion") or emotion
                    route_reason = "llm_override_low_confidence_rule"
                else:
                    entities = {**llm_entities, **entities}
                    route_reason = f"{route_reason}; llm_low_confidence_entity_merge"

        return AgentResponse(
            success=True,
            message=f"识别到意图：{intent.value}",
            data={
                "intent": intent.value,
                "confidence": round(float(confidence), 3),
                "candidate_intents": rule_result["candidate_intents"],
                "extracted_data": entities,
                "emotion_level": emotion,
                "route_reason": route_reason,
                "llm_used": llm_used,
                "original_content": message.content,
            },
            next_agent=self._target_agent(intent),
        )

    def _classify_by_rules(self, text: str) -> dict[str, Any]:
        entities = self._extract_entities(text)
        scores, matched_keywords = self._rule_scores(text)

        explicit_intent = self._explicit_intent(text, entities)
        if explicit_intent is not IntentType.UNKNOWN:
            scores[explicit_intent] = max(scores[explicit_intent], 0.72)

        candidates = self._candidate_intents(scores, matched_keywords)
        intent = explicit_intent if explicit_intent is not IntentType.UNKNOWN else self._top_intent(candidates)
        confidence = scores[intent]
        route_reason = "rule_priority" if explicit_intent is not IntentType.UNKNOWN else "rule_score"

        if confidence <= 0:
            intent = IntentType.UNKNOWN
            confidence = 0.2
            route_reason = "no_rule_match"

        return {
            "intent": intent,
            "confidence": min(float(confidence), 1.0),
            "candidate_intents": candidates,
            "extracted_data": entities,
            "emotion_level": self._detect_emotion(text),
            "route_reason": route_reason,
        }

    def _rule_scores(self, text: str) -> tuple[dict[IntentType, float], dict[IntentType, list[str]]]:
        lowered = text.lower()
        scores = {intent: 0.0 for intent in IntentType}
        matched_keywords: dict[IntentType, list[str]] = {intent: [] for intent in IntentType}

        for intent, keywords in self.keyword_map.items():
            hits = [kw for kw in keywords if kw.lower() in lowered]
            matched_keywords[intent] = hits
            scores[intent] = min(len(hits) * 0.25, 0.85)

        if re.search(r"\b[A-Z]{2}\d{9,13}\b", text, re.I):
            scores[IntentType.LOGISTICS] += 0.6
            matched_keywords[IntentType.LOGISTICS].append("tracking_number")
        if re.search(r"20\d{8,16}", text):
            scores[IntentType.ORDER] += 0.3
            matched_keywords[IntentType.ORDER].append("order_id")
        return {intent: min(score, 1.0) for intent, score in scores.items()}, matched_keywords

    def _candidate_intents(self, scores: dict[IntentType, float], matched_keywords: dict[IntentType, list[str]]) -> list[dict[str, Any]]:
        intents = [IntentType.ORDER, IntentType.LOGISTICS, IntentType.REFUND, IntentType.COMPLAINT, IntentType.UNKNOWN]
        ordered = sorted(intents, key=lambda item: (scores[item], self.priority[item]), reverse=True)
        return [
            {
                "intent": intent.value,
                "score": round(float(scores[intent]), 3),
                "matched_keywords": matched_keywords.get(intent, []),
            }
            for intent in ordered
        ]

    def _top_intent(self, candidates: list[dict[str, Any]]) -> IntentType:
        return self._intent_from_text(candidates[0]["intent"]) if candidates else IntentType.UNKNOWN

    def _explicit_intent(self, text: str, entities: dict[str, Any]) -> IntentType:
        lowered = text.lower()
        complaint_hits = ["投诉", "人工", "经理", "主管", "负责人", "真人", "12315", "曝光", "律师", "法院", "媒体"]
        refund_hits = ["退款", "退货", "退钱", "售后", "换货", "质量", "坏了", "破损", "不想要", "不喜欢", "七天"]
        logistics_hits = ["物流", "快递", "发货", "配送", "签收", "运单", "到哪", "到哪里", "没收到", "没有收到", "包裹", "轨迹"]
        order_hits = ["订单", "下单", "购买", "取消", "改地址", "修改地址", "地址", "商品"]

        if any(hit.lower() in lowered for hit in complaint_hits):
            return IntentType.COMPLAINT
        if any(hit.lower() in lowered for hit in refund_hits):
            return IntentType.REFUND
        if entities.get("tracking_number") or any(hit.lower() in lowered for hit in logistics_hits):
            return IntentType.LOGISTICS
        if entities.get("order_id") or any(hit.lower() in lowered for hit in order_hits):
            return IntentType.ORDER
        return IntentType.UNKNOWN

    def _extract_entities(self, text: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        order = re.search(r"(20\d{8,16})", text)
        tracking = re.search(r"\b([A-Z]{2}\d{9,13})\b", text, re.I)
        phone = re.search(r"(1[3-9]\d{9})", text)
        if order:
            data["order_id"] = order.group(1)
        if tracking:
            data["tracking_number"] = tracking.group(1).upper()
        if phone:
            data["phone"] = phone.group(1)

        refund_reason = self._refund_reason(text)
        if refund_reason:
            data["refund_reason"] = refund_reason

        requested_action = self._requested_action(text)
        if requested_action:
            data["requested_action"] = requested_action
        return data

    def _refund_reason(self, text: str) -> str | None:
        if any(k in text for k in ["质量", "坏", "破损", "故障", "有问题"]):
            return "quality_issue"
        if any(k in text for k in ["七天", "不想要", "不喜欢", "无理由"]):
            return "seven_day"
        if any(k in text for k in ["错发", "少发", "不是我要"]):
            return "wrong_item"
        if any(k in text for k in ["描述不符", "货不对板"]):
            return "not_as_described"
        return None

    def _requested_action(self, text: str) -> str | None:
        if any(k in text for k in ["取消", "不要了"]):
            return "cancel_order"
        if any(k in text for k in ["改地址", "修改地址", "换地址"]):
            return "change_address"
        if any(k in text for k in ["退款", "退货", "退钱", "换货", "赔付"]):
            return "apply_refund"
        if any(k in text for k in ["规则", "政策", "多久到账", "怎么退", "能退吗"]):
            return "policy_query"
        if any(k in text for k in ["物流", "快递", "到哪", "到哪里", "没收到", "没有收到", "签收", "包裹"]):
            return "track_shipment"
        if any(k in text for k in ["投诉", "人工", "经理", "主管", "负责人", "真人"]):
            return "escalate_or_complain"
        if any(k in text for k in ["查", "看看", "查询"]):
            return "query"
        return None

    def _detect_emotion(self, text: str) -> dict[str, Any]:
        angry = sum(text.count(k) for k in ["生气", "愤怒", "垃圾", "太差", "曝光", "投诉", "差评"])
        urgent = sum(text.count(k) for k in ["马上", "立刻", "赶紧", "现在", "急"])
        total = angry * 2 + urgent
        level = "high" if total >= 4 else "medium" if total >= 2 else "low"
        return {"level": level, "scores": {"angry": angry, "urgent": urgent}, "total_score": total}

    def _should_try_llm(self, rule_result: dict[str, Any]) -> bool:
        if not self.llm:
            return False
        candidates = rule_result.get("candidate_intents", [])
        confidence = float(rule_result.get("confidence", 0) or 0)
        if confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return True
        if len(candidates) < 2:
            return False
        top = float(candidates[0]["score"])
        second = float(candidates[1]["score"])
        return (top - second) < self.AMBIGUITY_DELTA

    def _intent_from_text(self, value: str) -> IntentType:
        try:
            return IntentType(value)
        except ValueError:
            return IntentType.UNKNOWN

    def _target_agent(self, intent: IntentType) -> str | None:
        return {
            IntentType.ORDER: "order",
            IntentType.LOGISTICS: "logistics",
            IntentType.REFUND: "refund",
            IntentType.COMPLAINT: "complaint",
            IntentType.UNKNOWN: None,
        }[intent]
