from __future__ import annotations

import json
import socket
import threading
from typing import Any

from emergence.admin.protocol import (
    AdminResponse,
    ProtocolError,
    decode_response_line,
)
from emergence.admin.snapshot_api import (
    build_admin_snapshot,
    build_artifacts_payload,
    build_events_payload,
    build_goal_payload,
    build_inspect_payload,
    build_knowledge_artifact_payload,
    build_knowledge_payload,
    build_physical_artifact_payload,
    build_space_desktop_payload,
    build_spaces_payload,
    build_timeline_payload,
    build_trace_payload,
)
from emergence.kernel.kernel import Kernel

_DEFAULT_HOST = "127.0.0.1"


class AdminServer:
    """
    Local TCP admin API for a running kernel.

    Handles one request per connection using newline-delimited JSON.
    """

    def __init__(
        self,
        kernel: Kernel,
        *,
        host: str = _DEFAULT_HOST,
        port: int = 0,
    ) -> None:
        self._kernel = kernel
        self._host = host
        self._port = port
        self._bound_port: int | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._server_socket: socket.socket | None = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        if self._bound_port is None:
            raise RuntimeError("admin server is not started")
        return self._bound_port

    def start(self) -> None:
        if self._thread is not None:
            return

        self._server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )
        self._server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )
        self._server_socket.bind((self._host, self._port))
        self._server_socket.listen(5)
        self._bound_port = self._server_socket.getsockname()[1]

        self._thread = threading.Thread(
            target=self._serve_forever,
            name="eos-admin-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._bound_port = None

    def _serve_forever(self) -> None:
        assert self._server_socket is not None

        while True:
            try:
                conn, _addr = self._server_socket.accept()
            except OSError:
                break

            with conn:
                self._handle_connection(conn)

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            raw = _read_line(conn)
            response = self._dispatch(raw)
        except ProtocolError as exc:
            response = AdminResponse(
                request_id="",
                ok=False,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - admin boundary
            response = AdminResponse(
                request_id="",
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        conn.sendall((response.to_json() + "\n").encode("utf-8"))

    def _dispatch(self, raw: bytes) -> AdminResponse:
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ProtocolError("invalid JSON request") from exc

        request_id = str(data.get("id", ""))
        method = str(data.get("method", ""))
        params = data.get("params") or {}

        if not method:
            return AdminResponse(
                request_id=request_id,
                ok=False,
                error="missing method",
            )

        with self._lock:
            if method == "ping":
                result = {"status": "ok"}
            elif method == "snapshot":
                result = build_admin_snapshot(self._kernel)
            elif method == "approve":
                request_key = str(params.get("request_id", ""))
                if not request_key:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing request_id",
                    )
                self._kernel.grant_user_approval(request_key)
                result = {"request_id": request_key, "granted": True}
            elif method == "goals":
                result = {"goals": self._kernel.context.goal_registry.list_views()}
            elif method == "goal.get":
                goal_id = str(params.get("goal_id", ""))
                if not goal_id:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing goal_id",
                    )
                try:
                    result = build_goal_payload(self._kernel, goal_id)
                except KeyError:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error=f"goal not found: {goal_id}",
                    )
            elif method == "knowledge.list":
                result = build_knowledge_payload(
                    self._kernel,
                    goal_id=str(params.get("goal_id", "")) or None,
                    artifact_type=str(params.get("artifact_type", "")) or None,
                )
            elif method == "knowledge.get":
                artifact_id = str(params.get("artifact_id", ""))
                if not artifact_id:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing artifact_id",
                    )
                try:
                    result = build_knowledge_artifact_payload(
                        self._kernel,
                        artifact_id,
                    )
                except KeyError:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error=f"artifact not found: {artifact_id}",
                    )
            elif method == "artifacts.list":
                result = build_artifacts_payload(
                    self._kernel,
                    goal_id=str(params.get("goal_id", "")) or None,
                    artifact_type=str(params.get("artifact_type", "")) or None,
                    space_id=str(params.get("space_id", "")) or None,
                    query=str(params.get("query", "")) or None,
                )
            elif method == "artifacts.get":
                artifact_id = str(params.get("artifact_id", ""))
                if not artifact_id:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing artifact_id",
                    )
                try:
                    result = build_physical_artifact_payload(
                        self._kernel,
                        artifact_id,
                    )
                except KeyError:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error=f"artifact not found: {artifact_id}",
                    )
            elif method in {"timeline.list", "goal.timeline"}:
                goal_id = str(params.get("goal_id", "")) or None
                if method == "goal.timeline" and not goal_id:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing goal_id",
                    )
                try:
                    result = build_timeline_payload(
                        self._kernel,
                        goal_id=goal_id,
                        correlation_id=str(params.get("correlation_id", ""))
                        or None,
                        since=str(params.get("since", "")) or None,
                        until=str(params.get("until", "")) or None,
                    )
                except KeyError:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error=f"goal not found: {goal_id}",
                    )
            elif method == "event.inspect":
                event_id = str(params.get("event_id", ""))
                if not event_id:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing event_id",
                    )
                try:
                    result = build_inspect_payload(self._kernel, event_id)
                except KeyError:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error=f"event not found: {event_id}",
                    )
            elif method == "events.list":
                result = build_events_payload(
                    self._kernel,
                    goal_id=str(params.get("goal_id", "")) or None,
                    limit=int(params.get("limit", 50)),
                )
            elif method == "spaces":
                result = build_spaces_payload(self._kernel)
            elif method == "space.desktop":
                result = build_space_desktop_payload(
                    self._kernel,
                    space_id=str(params.get("space_id", "")) or None,
                )
            elif method == "trace":
                correlation_id = str(params.get("correlation_id", ""))
                if not correlation_id:
                    return AdminResponse(
                        request_id=request_id,
                        ok=False,
                        error="missing correlation_id",
                    )
                result = build_trace_payload(
                    self._kernel,
                    correlation_id,
                )
            else:
                return AdminResponse(
                    request_id=request_id,
                    ok=False,
                    error=f"unknown method: {method}",
                )

        return AdminResponse(
            request_id=request_id,
            ok=True,
            result=result,
        )


def _read_line(conn: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        raise ProtocolError("empty request")
    return b"".join(chunks).split(b"\n", 1)[0]
