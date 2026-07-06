"""
Research Assistant — end-to-end cognitive application.

Orchestrates: plan → research → evaluate → approval → report.

Long-running, checkpointed, and fully observable via the event log.
"""

from __future__ import annotations

import uuid

from emergence.apps.long_running_runtime import get_stage, set_stage
from emergence.core.process_context import ProcessContext
from emergence.memory.memory_category import MemoryCategory
from emergence.tools.json_utils import extract_json


def _goal_state_get(context: ProcessContext, key: str, default=None):
    if context.goal_id is not None:
        scoped = context.state.get(f"goal:{context.goal_id}:{key}")
        if scoped is not None:
            return scoped
    return context.state.get(key, default)


def run(context: ProcessContext) -> str:
    """
    Multi-stage research pipeline:

    0. Plan tasks via LLM
    1. Research topic via LLM + RAG
    2. Evaluate findings via LLM
    3. Request user approval (optional auto-approve)
    4. Generate final report
    """
    topic = _goal_state_get(context, "research_topic", "EmergenceOS")
    stage = get_stage(context)

    # Chain stages in a single execution (orchestrator pattern)
    if stage == 0:
        _stage_plan(context, topic)
        stage = 1

    if stage == 1:
        _stage_research(context, topic)
        stage = 2

    if stage == 2:
        _stage_evaluate(context)
        stage = 3

    if stage == 3:
        _stage_approval(context)
        stage = 4

    if stage == 4:
        return _stage_report(context, topic)

    context.state.set("pipeline_status", "completed")
    return context.state.get("research_report", "done")


def _stage_plan(context: ProcessContext, topic: str) -> None:
    prompt = (
        f"Decompose this research goal into a JSON array of tasks:\n\n"
        f"Goal: Research and report on '{topic}'\n\n"
        f"Return ONLY JSON with name, process_definition_name, "
        f"dependencies, priority, expected_output fields."
    )

    result = context.tools.invoke(
        "llm.chat",
        {"prompt": prompt, "system": "Output valid JSON arrays only."},
    )
    if not result.success:
        raise RuntimeError(f"Planning failed: {result.error}")

    specs = extract_json(result.result) if isinstance(result.result, str) else result.result
    context.memory.store("task_specs", str(specs), category=MemoryCategory.WORKING)
    context.state.set("pipeline_status", "planned")
    set_stage(context, 1)


def _stage_research(context: ProcessContext, topic: str) -> None:
    rag = context.tools.invoke("memory.search", {"query": topic, "top_k": 3})
    prior = ""
    if rag.success and rag.result:
        hits = rag.result.get("results", [])
        prior = "\n".join(f"- {h['text'][:200]}" for h in hits)

    prompt = f"Research thoroughly: {topic}\n"
    if prior:
        prompt += f"\nPrior context:\n{prior}\n"
    prompt += "\nProvide detailed findings."

    result = context.tools.invoke(
        "llm.chat",
        {"prompt": prompt, "system": "You are a research assistant."},
    )
    if not result.success:
        raise RuntimeError(f"Research failed: {result.error}")

    findings = result.result
    context.memory.store("findings", findings, category=MemoryCategory.EPISODIC)
    context.state.set("research_findings", findings)
    context.state.set("pipeline_status", "researched")
    set_stage(context, 2)


def _stage_evaluate(context: ProcessContext) -> None:
    findings = context.state.get("research_findings", "")

    result = context.tools.invoke(
        "llm.chat",
        {
            "prompt": (
                f"Evaluate these findings. Return JSON with score, "
                f"feedback, approved fields.\n\n{findings}"
            ),
            "system": "Output valid JSON only.",
        },
    )
    if not result.success:
        raise RuntimeError(f"Evaluation failed: {result.error}")

    raw = result.result
    evaluation = extract_json(raw) if isinstance(raw, str) else raw
    score = int(evaluation.get("score", 5))
    approved = bool(evaluation.get("approved", score >= 6))

    context.state.set("evaluation", f"score={score}/10")
    context.state.set("evaluation_approved", approved)
    context.state.set("pipeline_status", "evaluated")
    set_stage(context, 3)


def _stage_approval(context: ProcessContext) -> None:
    auto = _goal_state_get(context, "auto_approve", True)
    if auto:
        context.state.set("pipeline_status", "approved")
        set_stage(context, 4)
        return

    request_id = context.memory.retrieve(
        "approval_id",
        category=MemoryCategory.WORKING,
    )
    if request_id is None:
        request_id = str(uuid.uuid4())
        context.memory.store(
            "approval_id",
            request_id,
            category=MemoryCategory.WORKING,
        )

    if context.state.get(f"approval:{request_id}"):
        context.state.set("pipeline_status", "approved")
        set_stage(context, 4)
        return

    context.state.set("pipeline_status", "awaiting_approval")
    context.wait_for_approval(
        request_id,
        message="Approve publishing the research report?",
    )
    context.state.set("pipeline_status", "approved")
    set_stage(context, 4)


def _stage_report(context: ProcessContext, topic: str) -> str:
    findings = context.state.get("research_findings", "")

    result = context.tools.invoke(
        "llm.chat",
        {
            "prompt": (
                f"Synthesize a final research report on '{topic}' "
                f"from these findings:\n\n{findings}"
            ),
            "system": "Write a clear, structured markdown report.",
        },
    )
    if not result.success:
        raise RuntimeError(f"Report generation failed: {result.error}")

    report = result.result
    context.state.set("research_report", report)
    context.memory.store("report", report, category=MemoryCategory.SEMANTIC)
    context.state.set("pipeline_status", "completed")
    set_stage(context, 5)
    return "report_complete"
