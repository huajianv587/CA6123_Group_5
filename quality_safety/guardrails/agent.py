from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from quality_safety.pii_redaction import PIIRedactor


@dataclass
class SafetyResult:
    text: str
    blocked: bool = False
    need_escalate: bool = False
    reason: str = ""
    pii_redacted: bool = False
    pii_counts: dict[str, int] = field(default_factory=dict)
    categories: list[str] = field(default_factory=list)
    matches: list[str] = field(default_factory=list)
    rag_context: str = ""
    rag_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    rule_score: float = 0.0
    emotion_score: int = 0
    malice_score: float = 0.0
    sdk_invoked: bool = False
    sdk_result: dict[str, Any] | None = None
    triggered_rules: list[str] = field(default_factory=list)
    block_reason: str = ""
    escalate_to_human: bool = False
    progressive_jailbreak: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "blocked": self.blocked,
            "need_escalate": self.need_escalate,
            "reason": self.reason,
            "pii_redacted": self.pii_redacted,
            "pii_counts": self.pii_counts,
            "categories": self.categories,
            "matches": self.matches,
            "risk_level": self.risk_level,
            "rule_score": self.rule_score,
            "emotion_score": self.emotion_score,
            "malice_score": self.malice_score,
            "sdk_invoked": self.sdk_invoked,
            "sdk_result": self.sdk_result,
            "triggered_rules": self.triggered_rules,
            "block_reason": self.block_reason,
            "escalate_to_human": self.escalate_to_human,
            "progressive_jailbreak": self.progressive_jailbreak,
            "rag_context": self.rag_context,
            "rag_sources": self.rag_sources,
            "metadata": self.metadata,
        }


class QualitySafetyAgent:
    EMOTION_MEDIUM_THRESHOLD = 3
    EMOTION_HIGH_THRESHOLD = 8
    RULE_SCORE_HIGH_THRESHOLD = 7.0
    RULE_SCORE_MEDIUM_THRESHOLD = 3.0
    SENSITIVE_OPERATION_KEYWORDS = [
        "退款",
        "退货",
        "查询数据",
        "修改规则",
        "改订单",
        "查账户",
        "改地址",
        "取消订单",
        "数据查询",
    ]
    VAGUE_COMMITMENT_PATTERNS = [
        "我尽力",
        "我试试",
        "也许可以",
        "可能会",
        "不一定",
        "说不准",
        "看情况",
        "再说吧",
    ]

    def __init__(self, retriever=None):
        self.redactor = PIIRedactor()
        self.retriever = retriever
        self.block_patterns: dict[str, list[re.Pattern[str]]] = {
            "prompt_injection": [
                re.compile(pattern, re.I)
                for pattern in [
                    r"ignore (all )?(previous|prior) instructions",
                    r"forget (all )?(previous|prior) instructions",
                    r"system\s*:",
                    r"developer message",
                    r"reveal (your|the) (system )?prompt",
                    r"print (your|the) (system )?prompt",
                    r"you are now",
                    r"\bDAN\b",
                    r"bypass",
                    r"扮演一个没有限制",
                    r"覆盖指令",
                    r"重置角色",
                    r"越狱",
                    r"忽略.*(之前|以上|系统).*指令",
                    r"透露.*(系统|开发者).*提示",
                ]
            ],
            "credential_request": [
                re.compile(pattern, re.I)
                for pattern in [
                    r"service[_ -]?role",
                    r"api[_ -]?key",
                    r"database password",
                    r"supabase.*key",
                    r"密钥",
                    r"密码",
                ]
            ],
        }
        self.warning_patterns: dict[str, list[re.Pattern[str]]] = {
            "fraud_risk": [
                re.compile(pattern, re.I)
                for pattern in [
                    r"刷单",
                    r"骗保",
                    r"伪造",
                    r"薅羊毛",
                    r"fake evidence",
                    r"chargeback abuse",
                ]
            ],
            "repeated_complaint": [
                re.compile(pattern, re.I)
                for pattern in [r"第三次", r"又来", r"反复", r"多次", r"一直没人处理"]
            ],
            "malicious_pressure": [
                re.compile(pattern, re.I)
                for pattern in [
                    r"不走流程",
                    r"跳过审核",
                    r"绕过系统",
                    r"私下解决",
                    r"后台帮我",
                    r"你有权限",
                    r"直接在系统里",
                    r"你不帮我就是违法",
                    r"必须满足我",
                    r"不满足就投诉你",
                ]
            ],
        }
        self.forbidden_commitments = {
            "一定赔偿": "将按平台规则审核处理",
            "保证赔偿": "将按平台规则审核处理",
            "无限额赔偿": "在平台规则范围内协助处理",
            "立刻到账": "按支付渠道时效到账",
            "马上退款": "提交后按审核和支付渠道时效处理",
        }

    def review(self, text: str, context: dict | None = None) -> SafetyResult:
        context = context or {}
        report = self.redactor.redact_with_report(text)
        reviewed = report.text
        rewritten = []
        for phrase, replacement in self.forbidden_commitments.items():
            if phrase in reviewed:
                reviewed = reviewed.replace(phrase, replacement)
                rewritten.append(phrase)

        escalation_reasons = []
        if context.get("need_escalate"):
            escalation_reasons.append(context.get("escalate_reason") or "business_agent_requested_human_review")
        escalation_reasons.extend(self.escalation_reasons(context))

        emotion_score = self._normalise_emotion_score(context.get("emotion_score", 0))
        output_warnings = [pattern for pattern in self.VAGUE_COMMITMENT_PATTERNS if pattern in reviewed]
        if output_warnings and emotion_score >= self.EMOTION_MEDIUM_THRESHOLD:
            reviewed += "\n\n以上为标准处理流程说明，具体结果以系统审核为准，客服无法提前承诺最终结论。"

        return SafetyResult(
            text=reviewed,
            need_escalate=bool(escalation_reasons),
            reason="; ".join(dict.fromkeys(reason for reason in escalation_reasons if reason)),
            pii_redacted=report.redacted,
            pii_counts=report.counts,
            risk_level="medium" if escalation_reasons else "low",
            emotion_score=emotion_score,
            triggered_rules=list(dict.fromkeys(escalation_reasons + output_warnings)),
            escalate_to_human=bool(escalation_reasons),
            metadata={
                "unsafe_commitments_rewritten": rewritten,
                "vague_commitments_detected": output_warnings,
                "review_stage": "output",
            },
        )

    def check_input(
        self,
        text: str,
        emotion_score: int | float | dict[str, Any] = 0,
        session_history: list[dict[str, Any]] | None = None,
    ) -> SafetyResult:
        report = self.redactor.redact_with_report(text)
        emotion = self._normalise_emotion_score(emotion_score)
        categories: list[str] = []
        matches: list[str] = []
        for category, patterns in self.block_patterns.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    categories.append(category)
                    matches.append(match.group(0))
                    break
        for category, patterns in self.warning_patterns.items():
            if any(pattern.search(text) for pattern in patterns):
                categories.append(category)

        blocked = any(category in {"prompt_injection", "credential_request"} for category in categories)
        reason = ""
        if "prompt_injection" in categories:
            reason = "prompt_injection_detected"
        elif "credential_request" in categories:
            reason = "credential_exfiltration_attempt"

        progressive = self._detect_progressive_jailbreak(text, session_history or [])
        if progressive:
            categories.append("progressive_jailbreak")

        triggered_rules = list(dict.fromkeys(categories))
        malice_score = self._malice_score(triggered_rules, progressive)
        rule_score = self._rule_score(emotion, malice_score, triggered_rules)
        if not blocked and (rule_score > self.RULE_SCORE_HIGH_THRESHOLD or progressive):
            blocked = True
            reason = "high_risk_guardrail_detected"

        risk_level = self._risk_level(rule_score, blocked)
        need_escalate = (
            not blocked
            and any(category in {"fraud_risk", "repeated_complaint", "malicious_pressure"} for category in categories)
        )
        block_reason = self.blocked_response(reason) if blocked else ""

        return SafetyResult(
            text=report.text,
            blocked=blocked,
            need_escalate=need_escalate,
            reason=reason,
            pii_redacted=report.redacted,
            pii_counts=report.counts,
            categories=triggered_rules,
            matches=matches,
            risk_level=risk_level,
            rule_score=rule_score,
            emotion_score=emotion,
            malice_score=malice_score,
            triggered_rules=triggered_rules,
            block_reason=block_reason,
            escalate_to_human=need_escalate or (blocked and reason == "high_risk_guardrail_detected"),
            progressive_jailbreak=progressive,
            metadata={"review_stage": "input"},
        )

    def check_sensitive_operation(self, content: str, emotion_score: int | float | dict[str, Any] = 0) -> str | None:
        emotion = self._normalise_emotion_score(emotion_score)
        if emotion < self.EMOTION_MEDIUM_THRESHOLD:
            return None
        hit_ops = [keyword for keyword in self.SENSITIVE_OPERATION_KEYWORDS if keyword in content]
        if not hit_ops:
            return None
        ops = "、".join(dict.fromkeys(hit_ops))
        return (
            f"您提到的【{ops}】操作需要通过标准流程处理，客服无法直接在对话中越权执行。\n\n"
            "请通过 App 内「我的订单」进入对应订单发起申请，或提供订单号，我可以协助您进入正式处理流程。"
        )

    def check_output(self, response: str, emotion_score: int | float | dict[str, Any] = 0) -> str:
        result = self.review(response, {"emotion_score": self._normalise_emotion_score(emotion_score)})
        return result.text

    def retrieve_context(self, query: str, intent: str | None = None, top_k: int = 2) -> SafetyResult:
        if not self.retriever:
            return SafetyResult(text=query)
        categories = [intent] if intent in {"order", "logistics", "refund", "complaint"} else []
        categories.append("safety")
        seen: set[str] = set()
        results = []
        for category in categories:
            for item in self.retriever.retrieve(query=query, top_k=top_k, category=category):
                if item.doc_id not in seen:
                    seen.add(item.doc_id)
                    results.append(item)
        return SafetyResult(
            text=query,
            rag_context=self.retriever.format_context(results, max_chars=600) if results else "",
            rag_sources=[item.doc_id for item in results],
            metadata={"review_stage": "rag_context", "categories": categories},
        )

    def escalation_reasons(self, context: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        route_data = context.get("route_data") or {}
        response_data = context.get("response_data") or {}
        user_input = context.get("user_input") or ""

        confidence = route_data.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.55:
            reasons.append("low_confidence_routing")

        amount = response_data.get("amount")
        if isinstance(amount, (int, float)) and amount >= 5000:
            reasons.append("high_value_refund_requires_human_review")

        emotion = response_data.get("emotion_analysis") or route_data.get("emotion_level") or {}
        if isinstance(emotion, dict):
            score = emotion.get("total_score") or 0
            level = emotion.get("level")
            if level == "high" or (isinstance(score, (int, float)) and score >= 6):
                reasons.append("high_negative_emotion")

        if any(word in user_input for word in ["丢件", "遗失", "没收到", "签收但没收到"]):
            if route_data.get("intent") == "logistics" or context.get("intent") == "logistics":
                reasons.append("logistics_exception_human_check")

        input_categories = context.get("input_categories") or []
        if "fraud_risk" in input_categories:
            reasons.append("suspected_fraud_risk")
        if "repeated_complaint" in input_categories:
            reasons.append("repeated_complaint")
        if "malicious_pressure" in input_categories:
            reasons.append("malicious_pressure_requires_human_review")

        return reasons

    def blocked_response(self, reason: str) -> str:
        if reason == "credential_exfiltration_attempt":
            return "出于安全原因，我不能提供或处理数据库密钥、API key、系统提示词等敏感凭证。请改为描述需要完成的业务操作。"
        if reason == "high_risk_guardrail_detected":
            return "您的请求触发了安全检测，当前无法自动处理。已为您优先安排人工客服介入，请稍候。"
        return "出于安全原因，我不能执行绕过系统规则、忽略指令或泄露内部提示词的请求。请直接说明您的订单、物流、退款或投诉问题。"

    def _normalise_emotion_score(self, emotion_score: int | float | dict[str, Any] | None) -> int:
        if isinstance(emotion_score, dict):
            emotion_score = emotion_score.get("score") or emotion_score.get("total_score") or 0
        if not isinstance(emotion_score, (int, float)):
            return 0
        return max(0, min(10, int(emotion_score)))

    def _detect_progressive_jailbreak(self, content: str, session_history: list[dict[str, Any]]) -> bool:
        signals = [
            "不走流程",
            "跳过审核",
            "绕过系统",
            "后台帮我",
            "你有权限",
            "ignore previous",
            "system prompt",
            "忽略之前",
        ]
        user_messages = [item.get("content", "") for item in session_history if item.get("role") == "user"][-3:]
        messages = user_messages + [content]
        return sum(any(signal.lower() in message.lower() for signal in signals) for message in messages) >= 2

    def _malice_score(self, categories: list[str], progressive: bool) -> float:
        weights = {
            "prompt_injection": 10.0,
            "credential_request": 10.0,
            "malicious_pressure": 5.0,
            "fraud_risk": 5.0,
            "repeated_complaint": 2.0,
            "progressive_jailbreak": 7.0,
        }
        score = max((weights.get(category, 0.0) for category in categories), default=0.0)
        if progressive:
            score = max(score, 7.0)
        return min(score, 10.0)

    def _rule_score(self, emotion_score: int, malice_score: float, categories: list[str]) -> float:
        base = emotion_score * 0.4 + malice_score * 0.6
        bonus = max(0, len(categories) - 1) * 0.3
        return min(base + bonus, 10.0)

    def _risk_level(self, rule_score: float, blocked: bool) -> str:
        if blocked or rule_score > self.RULE_SCORE_HIGH_THRESHOLD:
            return "high"
        if rule_score >= self.RULE_SCORE_MEDIUM_THRESHOLD:
            return "medium"
        return "low"


GuardResult = SafetyResult
GuardRail = QualitySafetyAgent
