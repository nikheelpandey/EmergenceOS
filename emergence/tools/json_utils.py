"""Helpers for parsing structured output from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """
    Parse JSON from an LLM response that may include markdown or prose.

    Tries direct parse, fenced code blocks, then bracket scanning.
    """
    text = text.strip()
    if not text:
        raise ValueError("Empty LLM response — expected JSON.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
