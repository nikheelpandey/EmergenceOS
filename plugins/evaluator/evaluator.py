"""
Evaluator plugin — scores research output via LLM.

Emits EVALUATION_COMPLETED with score and approval status.
"""

from __future__ import annotations

from emergence.core.process_context import ProcessContext
from emergence.events.user_events import EvaluationCompletedEvent
from emergence.tools.json_utils import extract_json


def run(context: ProcessContext) -> str:
    findings = context.state.get("research_findings")
    if findings is None:
        raise RuntimeError("No research findings available for evaluation")

    result = context.tools.invoke(
        "llm.chat",
        {
            "prompt": (
                f"Evaluate the following research findings. "
                f"Return JSON with score (1-10), feedback (string), "
                f"and approved (boolean).\n\n{findings}"
            ),
            "system": "You are a quality evaluator. Output valid JSON only.",
        },
    )

    if not result.success:
        raise RuntimeError(f"Evaluation LLM call failed: {result.error}")

    raw = result.result
    evaluation = extract_json(raw) if isinstance(raw, str) else raw

    score = int(evaluation.get("score", 5))
    feedback = evaluation.get("feedback", "")
    approved = bool(evaluation.get("approved", score >= 6))

    summary = f"score={score}/10: {feedback}"
    context.state.set("evaluation", summary)
    context.state.set("evaluation_score", score)
    context.state.set("evaluation_approved", approved)

    context.event_bus.publish(
        EvaluationCompletedEvent(
            score=score,
            approved=approved,
            source_process=context.process_id,
            payload={
                "score": score,
                "feedback": feedback,
                "approved": approved,
            },
        )
    )

    return summary
