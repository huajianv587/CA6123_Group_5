from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Pattern


@dataclass
class RedactionReport:
    text: str
    redacted: bool
    counts: dict[str, int] = field(default_factory=dict)


class PIIRedactor:
    def __init__(self):
        self.patterns: list[tuple[str, Pattern[str], str | Callable[[re.Match], str]]] = [
            ("phone", re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)"), self._mask_phone),
            (
                "email",
                re.compile(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
                r"\1***\2",
            ),
            ("credit_card", re.compile(r"(?<!\d)(\d{4})[ -]?(\d{4})[ -]?(\d{4})[ -]?(\d{4})(?!\d)"), r"\1 **** **** \4"),
            ("id_card", re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)"), r"\1********\2"),
            ("order_id", re.compile(r"(?<!\d)(20\d{4})\d{4,10}(?!\d)"), r"\1****"),
            ("tracking_number", re.compile(r"\b([A-Z]{2}\d{3})\d{4,10}\b", re.I), r"\1****"),
            (
                "address",
                re.compile(r"(收货地址[:：]\s*)([^\n，,。；;]+(?:省|市|区|县|镇|街道|路|号|室)[^\n。；;]*)"),
                r"\1[ADDRESS_REDACTED]",
            ),
        ]

    def redact(self, text: str) -> str:
        return self.redact_with_report(text).text

    def redact_with_report(self, text: str) -> RedactionReport:
        counts: dict[str, int] = {}
        redacted_text = text
        for label, pattern, repl in self.patterns:
            redacted_text, count = pattern.subn(repl, redacted_text)
            if count:
                counts[label] = counts.get(label, 0) + count
        return RedactionReport(text=redacted_text, redacted=bool(counts), counts=counts)

    def _mask_phone(self, match: re.Match) -> str:
        value = match.group(1)
        return value[:3] + "****" + value[-4:]
