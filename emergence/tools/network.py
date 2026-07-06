from __future__ import annotations

import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from emergence.core.ids import ProcessID


def _allowed_hosts() -> set[str]:
    raw = os.environ.get("EMERGENCE_HTTP_ALLOWLIST", "127.0.0.1,localhost")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if host not in _allowed_hosts():
        raise PermissionError(
            f"host '{host}' not in EMERGENCE_HTTP_ALLOWLIST"
        )


def create_http_fetch_handler():
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        url = str(args.get("url", "")).strip()
        if not url:
            raise ValueError("url required")

        method = str(args.get("method", "GET")).upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            raise ValueError(f"unsupported method: {method}")

        _check_url(url)

        headers = args.get("headers") or {}
        body = args.get("body")
        timeout = float(args.get("timeout", 15.0))
        max_bytes = int(args.get("max_bytes", 1_048_576))

        data = None
        if body is not None:
            if isinstance(body, dict):
                import json

                data = json.dumps(body).encode("utf-8")
                headers = {**headers, "Content-Type": "application/json"}
            else:
                data = str(body).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers={str(k): str(v) for k, v in headers.items()},
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(max_bytes + 1)
                truncated = len(raw) > max_bytes
                if truncated:
                    raw = raw[:max_bytes]
                content_type = response.headers.get("Content-Type", "")
                try:
                    text = raw.decode("utf-8")
                    binary = False
                except UnicodeDecodeError:
                    text = raw.decode("latin-1")
                    binary = True
                return {
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "content": text,
                    "binary": binary,
                    "truncated": truncated,
                    "size_bytes": len(raw),
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read(max_bytes)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            return {
                "url": url,
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type", ""),
                "content": text,
                "error": str(exc),
                "size_bytes": len(raw),
            }

    return handler
