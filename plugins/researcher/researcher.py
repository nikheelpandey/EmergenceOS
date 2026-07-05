"""
Researcher plugin — gather findings via LLM and store in episodic memory.

Uses ``llm.chat`` for research and ``memory.search`` for RAG context.
"""

from __future__ import annotations

import json

from emergence.common.request import Request
from emergence.common.response import Response
from emergence.core.process_context import ProcessContext
from emergence.memory.memory_category import MemoryCategory


def run(context: ProcessContext) -> str:
    stage = context.memory.retrieve("stage", default=0)

    if stage == 0:
        return _do_research(context)

    if context.mailboxes.pending() > 0:
        message = context.mailboxes.receive()
        if isinstance(message, Request):
            topic = message.payload.get("topic", "general research")
            context.memory.store("topic", topic, category=MemoryCategory.WORKING)
            context.memory.store("requester", message.sender_pid, category=MemoryCategory.WORKING)
            context.memory.store("correlation", str(message.correlation_id), category=MemoryCategory.WORKING)
            return _do_research(context)

    context.wait_for_message()
    return "researcher_waiting"


def _do_research(context: ProcessContext) -> str:
    topic = (
        context.memory.retrieve("topic", category=MemoryCategory.WORKING)
        or context.state.get("research_topic", "EmergenceOS architecture")
    )

    rag = context.tools.invoke(
        "memory.search",
        {"query": topic, "top_k": 3},
    )
    prior_context = ""
    if rag.success and rag.result:
        hits = rag.result.get("results", [])
        if hits:
            prior_context = "\n".join(
                f"- {h['text'][:200]}" for h in hits
            )

    prompt = (
        f"Research the following topic thoroughly:\n\n{topic}\n\n"
    )
    if prior_context:
        prompt += f"Prior findings from memory:\n{prior_context}\n\n"
    prompt += "Provide detailed research findings."

    result = context.tools.invoke(
        "llm.chat",
        {
            "prompt": prompt,
            "system": "You are a research assistant. Be thorough and factual.",
        },
    )

    if not result.success:
        raise RuntimeError(f"Research LLM call failed: {result.error}")

    findings = result.result
    context.memory.store(
        "findings",
        findings,
        category=MemoryCategory.EPISODIC,
    )
    context.state.set("research_findings", findings)

    requester = context.memory.retrieve("requester", category=MemoryCategory.WORKING)
    if requester:
        correlation = context.memory.retrieve("correlation", category=MemoryCategory.WORKING)
        context.mailboxes.send(
            Response(
                sender_pid=str(context.process_id),
                recipient_pid=requester,
                payload={"findings": findings},
                correlation_id=correlation,
                result=findings,
            )
        )

    context.memory.store("stage", 1)
    return "research_complete"
