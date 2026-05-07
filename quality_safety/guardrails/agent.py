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


class QualitySafetyAgent:
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

        return SafetyResult(
            text=reviewed,
            need_escalate=bool(escalation_reasons),
            reason="; ".join(dict.fromkeys(reason for reason in escalation_reasons if reason)),
            pii_redacted=report.redacted,
            pii_counts=report.counts,
            metadata={
                "unsafe_commitments_rewritten": rewritten,
                "review_stage": "output",
            },
        )

    def check_input(self, text: str) -> SafetyResult:
        report = self.redactor.redact_with_report(text)
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

        return SafetyResult(
            text=report.text,
            blocked=blocked,
            need_escalate=not blocked and any(category in {"fraud_risk", "repeated_complaint"} for category in categories),
            reason=reason,
            pii_redacted=report.redacted,
            pii_counts=report.counts,
            categories=list(dict.fromkeys(categories)),
            matches=matches,
            metadata={"review_stage": "input"},
        )

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

        return reasons

    def blocked_response(self, reason: str) -> str:
        if reason == "credential_exfiltration_attempt":
            return "出于安全原因，我不能提供或处理数据库密钥、API key、系统提示词等敏感凭证。请改为描述需要完成的业务操作。"
        return "出于安全原因，我不能执行绕过系统规则、忽略指令或泄露内部提示词的请求。请直接说明您的订单、物流、退款或投诉问题。"
