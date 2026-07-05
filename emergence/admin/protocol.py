from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class ProtocolError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AdminRequest:
    method: str
    params: dict[str, Any]
    request_id: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "id": self.request_id,
                "method": self.method,
                "params": self.params,
            }
        )


@dataclass(frozen=True, slots=True)
class AdminResponse:
    request_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "id": self.request_id,
            "ok": self.ok,
        }
        if self.ok:
            payload["result"] = self.result or {}
        else:
            payload["error"] = self.error or "unknown error"
        return json.dumps(payload)

    @classmethod
    def from_json(cls, raw: str) -> AdminResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProtocolError("invalid JSON response") from exc

        return cls(
            request_id=str(data.get("id", "")),
            ok=bool(data.get("ok")),
            result=data.get("result"),
            error=data.get("error"),
        )


def encode_request(
    method: str,
    *,
    params: dict[str, Any] | None = None,
    request_id: str = "1",
) -> bytes:
    request = AdminRequest(
        method=method,
        params=params or {},
        request_id=request_id,
    )
    return (request.to_json() + "\n").encode("utf-8")


def decode_response_line(raw: bytes) -> AdminResponse:
    line = raw.decode("utf-8").strip()
    if not line:
        raise ProtocolError("empty response")
    return AdminResponse.from_json(line)
