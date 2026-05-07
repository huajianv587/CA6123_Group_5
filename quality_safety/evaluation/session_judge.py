from __future__ import annotations

from datetime import datetime
from typing import Any


QUADRANT_ACTIONS = {
    "resolved_satisfied": ("已解决·满意", "archive"),
    "resolved_unsatisfied": ("已解决·不满意", "review_solution"),
    "unresolved_satisfied": ("未解决·满意", "review_knowledge"),
    "unresolved_unsatisfied": ("未解决·不满意", "human_followup"),
}


class SessionJudge:
    def evaluate(self, session: dict[str, Any]) -> dict[str, Any]:
        messages = session.get("messages", [])
        traces = session.get("traces") or session.get("routing_trace") or []
        scores = self._emotion_scores(traces)
        resolved, satisfied, reason = self._rule_judge(messages, scores)
        key = f"{'resolved' if resolved else 'unresolved'}_{'satisfied' if satisfied else 'unsatisfied'}"
        label, action = QUADRANT_ACTIONS[key]
        return {
            "session_id": session.get("session_id", ""),
            "resolved": resolved,
            "satisfied": satisfied,
            "emotion_trend": self._emotion_trend(scores),
            "emotion_scores": scores,
            "quadrant": label,
            "recommended_action": action,
            "judge_reasoning": reason,
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    def _emotion_scores(self, traces: list[dict[str, Any]]) -> list[int]:
        scores = []
        for item in traces:
            score = item.get("router_emotion_score")
            if score is None:
                emotion = item.get("emotion") or item.get("emotion_level") or {}
                score = emotion.get("score") if isinstance(emotion, dict) else None
            if isinstance(score, (int, float)):
                scores.append(int(score))
        return scores

    def _emotion_trend(self, scores: list[int]) -> str:
        if len(scores) < 2:
            return "平稳"
        delta = scores[-1] - scores[0]
        if delta <= -2:
            return "好转"
        if delta >= 2:
            return "恶化"
        return "平稳"

    def _rule_judge(self, messages: list[dict[str, Any]], scores: list[int]) -> tuple[bool, bool, str]:
        last_assistant = next((item for item in reversed(messages) if item.get("role") == "assistant"), {})
        resolved = bool(last_assistant.get("success", True)) and not bool(last_assistant.get("need_escalate", False))
        last_score = scores[-1] if scores else 4
        satisfied = last_score < 6 and not bool(last_assistant.get("need_escalate", False))
        return resolved, satisfied, "规则降级判断"
