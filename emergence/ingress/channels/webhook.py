from __future__ import annotations

from typing import Any


class WebhookChannelAdapter:
    """Reference channel adapter: inbound webhook → goal submission."""

    def parse_inbound(self, payload: dict[str, Any]) -> str:
        for key in ("text", "message", "body", "description"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise ValueError("payload must include text, message, body, or description")

    def format_reply(self, goal_id: str, base_url: str) -> str:
        return (
            f"Goal created. Track progress: {base_url}/goals/{goal_id}"
        )
