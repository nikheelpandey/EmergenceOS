from __future__ import annotations

import socket
from typing import Any

from emergence.admin.paths import read_manifest
from emergence.admin.protocol import (
    ProtocolError,
    decode_response_line,
    encode_request,
)


class AdminConnectionError(Exception):
    pass


class AdminClient:
    """
    Client for the live kernel admin API.
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    @classmethod
    def connect(cls) -> AdminClient:
        manifest = read_manifest()
        if manifest is None:
            raise AdminConnectionError(
                "EmergenceOS is not running. Start it with: ./eos serve"
            )
        return cls(manifest.host, manifest.port)

    @classmethod
    def from_address(cls, host: str, port: int) -> AdminClient:
        return cls(host, port)

    def call(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        request_id: str = "1",
    ) -> dict[str, Any]:
        response = self._request(method, params=params, request_id=request_id)
        if not response.ok:
            raise AdminConnectionError(response.error or "admin request failed")
        return response.result or {}

    def ping(self) -> dict[str, Any]:
        return self.call("ping")

    def snapshot(self) -> dict[str, Any]:
        return self.call("snapshot")

    def approve(self, request_id: str) -> dict[str, Any]:
        return self.call(
            "approve",
            params={"request_id": request_id},
        )

    def trace(self, correlation_id: str) -> dict[str, Any]:
        return self.call(
            "trace",
            params={"correlation_id": correlation_id},
        )

    def _request(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        request_id: str = "1",
    ):
        try:
            with socket.create_connection(
                (self._host, self._port),
                timeout=5.0,
            ) as conn:
                conn.sendall(
                    encode_request(
                        method,
                        params=params,
                        request_id=request_id,
                    )
                )
                raw = _read_response_line(conn)
        except OSError as exc:
            raise AdminConnectionError(
                f"Could not connect to EmergenceOS admin API at "
                f"{self._host}:{self._port}: {exc}"
            ) from exc

        try:
            return decode_response_line(raw)
        except ProtocolError as exc:
            raise AdminConnectionError(str(exc)) from exc


def _read_response_line(conn: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        raise AdminConnectionError("empty response from admin server")
    return b"".join(chunks).split(b"\n", 1)[0]
