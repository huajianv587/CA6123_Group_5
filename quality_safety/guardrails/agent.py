from dataclasses import dataclass

from quality_safety.pii_redaction import PIIRedactor


@dataclass
class SafetyResult:
    text: str
    blocked: bool = False
    need_escalate: bool = False
    reason: str = ""


class QualitySafetyAgent:
    def __init__(self):
        self.redactor = PIIRedactor()
        self.forbidden_commitments = ["一定赔偿", "保证赔偿", "无限额赔偿", "立刻到账"]

    def review(self, text: str, context: dict | None = None) -> SafetyResult:
        context = context or {}
        redacted = self.redactor.redact(text)
        for phrase in self.forbidden_commitments:
            if phrase in redacted:
                redacted = redacted.replace(phrase, "将按平台规则审核处理")
        if context.get("need_escalate"):
            return SafetyResult(text=redacted, need_escalate=True, reason=context.get("escalate_reason", "requires_human_review"))
        return SafetyResult(text=redacted)
