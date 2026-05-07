from .scenarios import EVAL_SCENARIOS, SAFETY_SCENARIOS
from .session_judge import SessionJudge


def evaluate_quality_safety() -> dict:
    from .evaluator import evaluate_quality_safety as _evaluate_quality_safety

    return _evaluate_quality_safety()


__all__ = ["EVAL_SCENARIOS", "SAFETY_SCENARIOS", "SessionJudge", "evaluate_quality_safety"]
