from __future__ import annotations

import os


def expected_token() -> str | None:
    """Return configured API token, if any."""
    return os.environ.get("EMERGENCE_API_TOKEN") or None


def authorize(headers: dict[str, str]) -> bool:
    """Validate bearer token when EMERGENCE_API_TOKEN is set."""
    token = expected_token()
    if token is None:
        return True
    auth = headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True
    return headers.get("X-Emergence-Token") == token
