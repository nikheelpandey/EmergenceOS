from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from emergence.admin.snapshot_api import (
    build_admin_snapshot,
    build_artifacts_payload,
    build_events_payload,
    build_goal_payload,
    build_goal_policy_payload,
    build_goal_results_payload,
    build_inspect_payload,
    build_knowledge_artifact_payload,
    build_knowledge_payload,
    build_physical_artifact_payload,
    build_space_desktop_payload,
    build_spaces_payload,
    build_timeline_payload,
)
from emergence.core.event import Event, EventType
from emergence.cognitive.goal_registry import GoalNotRegisteredError
from emergence.core.ids import GoalID
from emergence.events.narrative import narrate_event
from emergence.ingress.channels.webhook import WebhookChannelAdapter
from emergence.ingress.goal_management import (
    GoalManagementError,
    archive_goal,
    cancel_goal,
    delete_goal,
    rerun_goal,
    update_goal,
)
from emergence.ingress.goal_submission import submit_goal
from emergence.ingress.http.auth import authorize
from emergence.kernel.kernel import Kernel

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765
_WEB_ROOT = Path(__file__).resolve().parents[3] / "web"
_GOAL_ID_RE = re.compile(
    r"^/goals/(?P<goal_id>[^/]+)(?P<suffix>/timeline|/knowledge|/artifacts|/processes|/stream|/results|/policy|/rerun|/cancel)?$"
)
_EVENT_ID_RE = re.compile(r"^/events/(?P<event_id>[^/]+)/inspect$")
_KNOWLEDGE_ID_RE = re.compile(r"^/knowledge/(?P<artifact_id>[^/]+)$")
_ARTIFACT_ID_RE = re.compile(r"^/artifacts/(?P<artifact_id>[^/]+)$")
_SPACE_ID_RE = re.compile(r"^/spaces/(?P<space_id>[^/]+)(?P<suffix>/desktop)?$")


class HttpIngressServer:
    """REST + static web UI for external clients."""

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
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._stream_lock = threading.Lock()
        self._stream_subscribers: dict[str, list[Any]] = {}
        self._channel = WebhookChannelAdapter()
        self._subscribe_events()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        if self._bound_port is None:
            raise RuntimeError("http ingress is not started")
        return self._bound_port

    def start(self) -> None:
        if self._thread is not None:
            return

        handler = _make_handler(self)
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._bound_port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="eos-http-ingress",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._bound_port = None

    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _subscribe_events(self) -> None:
        bus = self._kernel.context.event_bus

        def _on_event(event: Event) -> None:
            plugin = None
            if event.source_process is not None:
                ctx = self._kernel.context
                if ctx.process_table.exists(event.source_process):
                    plugin = (
                        ctx.process_table.get(event.source_process)
                        .definition.name
                    )
            narrative = narrate_event(event, plugin=plugin)
            if narrative is None:
                return
            goal_id = None
            if event.source_process is not None:
                gid = self._kernel.context.goal_registry.goal_for_process(
                    event.source_process
                )
                if gid is not None:
                    goal_id = str(gid)
            if goal_id is None:
                payload_goal = event.payload.get("goal_id")
                if payload_goal is not None:
                    goal_id = str(payload_goal)
            payload = {
                "event_id": str(event.event_id),
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "narrative": narrative,
                "goal_id": goal_id,
            }
            self._broadcast(goal_id or "*", payload)

        for event_type in EventType:
            bus.subscribe(event_type, _on_event)

    def _broadcast(self, key: str, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        with self._stream_lock:
            targets = list(self._stream_subscribers.get(key, []))
            targets.extend(self._stream_subscribers.get("*", []))
        for subscriber in targets:
            try:
                subscriber(message)
            except OSError:
                pass


def _make_handler(server: HttpIngressServer):
    kernel = server._kernel

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _headers_dict(self) -> dict[str, str]:
            return {k: v for k, v in self.headers.items()}

        def _send_json(
            self,
            payload: Any,
            *,
            status: int = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error_json(self, message: str, status: int) -> None:
            self._send_json({"error": message}, status=status)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}

        def _require_auth(self) -> bool:
            if authorize(self._headers_dict()):
                return True
            self._send_error_json("unauthorized", HTTPStatus.UNAUTHORIZED)
            return False

        def do_GET(self) -> None:  # noqa: N802
            if not self._require_auth():
                return
            path = urlparse(self.path).path
            query = parse_qs(urlparse(self.path).query)

            if path in {"/health", "/api/health"}:
                self._send_json({"status": "ok"})
                return

            if path in {"/system/snapshot", "/api/system/snapshot"}:
                self._send_json(build_admin_snapshot(kernel))
                return

            if path in {"/goals", "/api/goals"}:
                space_id = query.get("space_id", [None])[0]
                include_archived = query.get("include_archived", ["false"])[0].lower() in {
                    "1",
                    "true",
                    "yes",
                }
                goals = kernel.context.goal_registry.list_views(
                    space_id=space_id,
                    include_archived=include_archived,
                )
                self._send_json({"goals": goals})
                return

            if path in {"/events", "/api/events"}:
                goal_id = query.get("goal_id", [None])[0]
                limit = int(query.get("limit", ["50"])[0])
                self._send_json(
                    build_events_payload(
                        kernel,
                        goal_id=goal_id,
                        limit=limit,
                    )
                )
                return

            if path in {"/artifacts", "/api/artifacts"}:
                goal_id = query.get("goal_id", [None])[0]
                artifact_type = query.get("type", query.get("artifact_type", [None]))[0]
                space_id = query.get("space_id", [None])[0]
                search_query = query.get("q", query.get("query", [None]))[0]
                self._send_json(
                    build_artifacts_payload(
                        kernel,
                        goal_id=goal_id,
                        artifact_type=artifact_type,
                        space_id=space_id,
                        query=search_query,
                    )
                )
                return

            if path in {"/spaces", "/api/spaces"}:
                self._send_json(build_spaces_payload(kernel))
                return

            match = _ARTIFACT_ID_RE.match(path.replace("/api", "", 1))
            if match:
                try:
                    self._send_json(
                        build_physical_artifact_payload(
                            kernel,
                            match.group("artifact_id"),
                        )
                    )
                except KeyError:
                    self._send_error_json(
                        "artifact not found",
                        HTTPStatus.NOT_FOUND,
                    )
                return

            match = _KNOWLEDGE_ID_RE.match(path.replace("/api", "", 1))
            if match:
                try:
                    self._send_json(
                        build_knowledge_artifact_payload(
                            kernel,
                            match.group("artifact_id"),
                        )
                    )
                except KeyError:
                    self._send_error_json(
                        "artifact not found",
                        HTTPStatus.NOT_FOUND,
                    )
                return

            match = _EVENT_ID_RE.match(path.replace("/api", "", 1))
            if match:
                try:
                    self._send_json(
                        build_inspect_payload(
                            kernel,
                            match.group("event_id"),
                        )
                    )
                except KeyError:
                    self._send_error_json("event not found", HTTPStatus.NOT_FOUND)
                return

            match = _SPACE_ID_RE.match(path.replace("/api", "", 1))
            if match and match.group("suffix") == "/desktop":
                try:
                    self._send_json(
                        build_space_desktop_payload(
                            kernel,
                            match.group("space_id"),
                        )
                    )
                except KeyError:
                    self._send_error_json("space not found", HTTPStatus.NOT_FOUND)
                return

            match = _GOAL_ID_RE.match(path.replace("/api", "", 1))
            if match:
                goal_id = match.group("goal_id")
                suffix = match.group("suffix") or ""
                try:
                    if suffix == "/timeline":
                        self._send_json(
                            build_timeline_payload(kernel, goal_id=goal_id)
                        )
                    elif suffix == "/knowledge":
                        self._send_json(
                            build_knowledge_payload(kernel, goal_id=goal_id)
                        )
                    elif suffix == "/artifacts":
                        self._send_json(
                            build_artifacts_payload(kernel, goal_id=goal_id)
                        )
                    elif suffix == "/results":
                        self._send_json(
                            build_goal_results_payload(kernel, goal_id)
                        )
                    elif suffix == "/processes":
                        goal = build_goal_payload(kernel, goal_id)
                        snapshot = build_admin_snapshot(kernel)
                        process_ids = set(goal.get("process_ids", []))
                        processes = [
                            item
                            for item in snapshot["processes"]
                            if item["process_id"] in process_ids
                        ]
                        self._send_json(
                            {"goal_id": goal_id, "processes": processes}
                        )
                    elif suffix == "/policy":
                        self._send_json(build_goal_policy_payload(kernel, goal_id))
                    elif suffix == "/stream":
                        self._handle_sse(goal_id)
                    else:
                        self._send_json(build_goal_payload(kernel, goal_id))
                except KeyError:
                    self._send_error_json("goal not found", HTTPStatus.NOT_FOUND)
                return

            if path.startswith("/ws/goals/"):
                self._handle_websocket(path.removeprefix("/ws/goals/"))
                return

            self._serve_static(path)

        def do_POST(self) -> None:  # noqa: N802
            if not self._require_auth():
                return
            path = urlparse(self.path).path.replace("/api", "", 1)

            if path == "/goals":
                body = self._read_json()
                description = str(body.get("description", "")).strip()
                if not description:
                    self._send_error_json(
                        "description required",
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                result = submit_goal(
                    kernel,
                    description,
                    mode=str(body.get("mode", body.get("workload", "goal"))),
                    workload=body.get("workload"),
                    space_id=body.get("space_id"),
                    auto_approve=body.get("auto_approve"),
                    spend_preset=body.get("spend_preset"),
                    autonomy_preset=body.get("autonomy_preset"),
                    policy=body.get("policy") if isinstance(body.get("policy"), dict) else None,
                    config=body.get("config") if isinstance(body.get("config"), dict) else None,
                )
                self._send_json(
                    {
                        "goal_id": result.goal_id,
                        "description": result.description,
                        "mode": result.mode,
                        "process_id": result.process_id,
                        "message": result.message,
                        "policy": result.policy,
                        "tracking_url": (
                            f"{server.base_url()}/goals/{result.goal_id}"
                        ),
                    },
                    status=HTTPStatus.CREATED,
                )
                return

            if path == "/spaces":
                body = self._read_json()
                name = str(body.get("name", "")).strip()
                if not name:
                    self._send_error_json("name required", HTTPStatus.BAD_REQUEST)
                    return
                space = kernel.context.space_registry.create(name)
                self._send_json(
                    {
                        "space_id": space.space_id,
                        "name": space.name,
                    },
                    status=HTTPStatus.CREATED,
                )
                return

            if path.startswith("/spaces/") and path.endswith("/switch"):
                space_id = path.removeprefix("/spaces/").removesuffix("/switch")
                try:
                    space = kernel.context.space_registry.switch(space_id)
                except KeyError:
                    self._send_error_json("space not found", HTTPStatus.NOT_FOUND)
                    return
                self._send_json(
                    {"space_id": space.space_id, "name": space.name}
                )
                return

            if path == "/channels/webhook":
                body = self._read_json()
                try:
                    description = server._channel.parse_inbound(body)
                except ValueError as exc:
                    self._send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
                    return
                if not description:
                    self._send_error_json(
                        "empty message",
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                mode = "research" if description.lower().startswith("research") else "goal"
                if mode == "research":
                    description = description.split(" ", 1)[-1].strip() or description
                result = submit_goal(kernel, description, mode=mode)
                reply = server._channel.format_reply(
                    result.goal_id,
                    server.base_url(),
                )
                self._send_json(
                    {
                        "reply": reply,
                        "goal_id": result.goal_id,
                        "tracking_url": (
                            f"{server.base_url()}/goals/{result.goal_id}"
                        ),
                    },
                    status=HTTPStatus.CREATED,
                )
                return

            match = re.match(
                r"^/goals/(?P<goal_id>[^/]+)/schedule$",
                path,
            )
            if match:
                body = self._read_json()
                fire_at_raw = str(body.get("fire_at", ""))
                process_name = str(
                    body.get("process", body.get("process_definition_name", "job_worker"))
                )
                if not fire_at_raw:
                    self._send_error_json("fire_at required", HTTPStatus.BAD_REQUEST)
                    return
                goal_id = GoalID.from_string(match.group("goal_id"))
                if kernel.context.goal_registry.get(goal_id) is None:
                    self._send_error_json("goal not found", HTTPStatus.NOT_FOUND)
                    return
                entry = kernel.context.schedule_manager.register(
                    goal_id,
                    process_name,
                    datetime.fromisoformat(fire_at_raw),
                    description=str(body.get("description", "")),
                )
                self._send_json(
                    {
                        "schedule_id": entry.schedule_id,
                        "fire_at": entry.fire_at.isoformat(),
                    },
                    status=HTTPStatus.CREATED,
                )
                return

            match = re.match(r"^/approvals/(?P<request_id>[^/]+)$", path)
            if match:
                kernel.grant_user_approval(match.group("request_id"))
                self._send_json(
                    {
                        "request_id": match.group("request_id"),
                        "granted": True,
                    }
                )
                return

            match = _GOAL_ID_RE.match(path)
            if match and match.group("suffix") == "/rerun":
                try:
                    self._send_json(rerun_goal(kernel, match.group("goal_id")))
                except GoalNotRegisteredError:
                    self._send_error_json("goal not found", HTTPStatus.NOT_FOUND)
                except GoalManagementError as exc:
                    self._send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
                return

            match = _GOAL_ID_RE.match(path)
            if match and match.group("suffix") == "/cancel":
                try:
                    self._send_json(cancel_goal(kernel, match.group("goal_id")))
                except GoalNotRegisteredError:
                    self._send_error_json("goal not found", HTTPStatus.NOT_FOUND)
                return

            self._send_error_json("not found", HTTPStatus.NOT_FOUND)

        def do_PATCH(self) -> None:  # noqa: N802
            if not self._require_auth():
                return
            path = urlparse(self.path).path.replace("/api", "", 1)
            match = _GOAL_ID_RE.match(path)
            if not match or match.group("suffix"):
                self._send_error_json("not found", HTTPStatus.NOT_FOUND)
                return
            body = self._read_json()
            try:
                updated = update_goal(
                    kernel,
                    match.group("goal_id"),
                    description=body.get("description"),
                    spend_preset=body.get("spend_preset"),
                    autonomy_preset=body.get("autonomy_preset"),
                    auto_approve=body.get("auto_approve"),
                    policy=body.get("policy") if isinstance(body.get("policy"), dict) else None,
                )
            except GoalNotRegisteredError:
                self._send_error_json("goal not found", HTTPStatus.NOT_FOUND)
                return
            except GoalManagementError as exc:
                self._send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
                return
            self._send_json(updated)
            return

        def do_DELETE(self) -> None:  # noqa: N802
            if not self._require_auth():
                return
            path = urlparse(self.path).path.replace("/api", "", 1)
            query = parse_qs(urlparse(self.path).query)
            match = _GOAL_ID_RE.match(path)
            if not match or match.group("suffix"):
                self._send_error_json("not found", HTTPStatus.NOT_FOUND)
                return
            hard = query.get("hard", ["false"])[0].lower() in {"1", "true", "yes"}
            try:
                result = delete_goal(kernel, match.group("goal_id"), hard=hard)
            except GoalNotRegisteredError:
                self._send_error_json("goal not found", HTTPStatus.NOT_FOUND)
                return
            self._send_json(result)
            return

        def _serve_static(self, path: str) -> None:
            if path in {"/", "/ui", "/ui/"}:
                path = "/index.html"
            file_path = (_WEB_ROOT / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str(_WEB_ROOT.resolve())):
                self._send_error_json("not found", HTTPStatus.NOT_FOUND)
                return
            if not file_path.exists() or not file_path.is_file():
                self._send_error_json("not found", HTTPStatus.NOT_FOUND)
                return
            content = file_path.read_bytes()
            content_type, _ = mimetypes.guess_type(str(file_path))
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                content_type or "application/octet-stream",
            )
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _handle_sse(self, goal_id: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            def send_message(message: str) -> None:
                data = f"data: {message}\n\n".encode("utf-8")
                self.wfile.write(data)
                self.wfile.flush()

            with server._stream_lock:
                server._stream_subscribers.setdefault(goal_id, []).append(
                    send_message
                )
            try:
                send_message(json.dumps({"type": "connected", "goal_id": goal_id}))
                while True:
                    self.rfile.read(1)
            except Exception:
                pass
            finally:
                with server._stream_lock:
                    subs = server._stream_subscribers.get(goal_id, [])
                    if send_message in subs:
                        subs.remove(send_message)

        def _handle_websocket(self, goal_id: str) -> None:
            key = self.headers.get("Sec-WebSocket-Key")
            if key is None:
                self._send_error_json(
                    "websocket upgrade required",
                    HTTPStatus.BAD_REQUEST,
                )
                return
            accept = base64.b64encode(
                hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            ).decode()
            self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()

            def send_message(message: str) -> None:
                payload = message.encode("utf-8")
                frame = bytes([0x81, len(payload)]) + payload
                self.wfile.write(frame)
                self.wfile.flush()

            with server._stream_lock:
                server._stream_subscribers.setdefault(goal_id, []).append(
                    send_message
                )
            try:
                send_message(json.dumps({"type": "connected", "goal_id": goal_id}))
                while True:
                    chunk = self.rfile.read(1024)
                    if not chunk:
                        break
            except Exception:
                pass
            finally:
                with server._stream_lock:
                    subs = server._stream_subscribers.get(goal_id, [])
                    if send_message in subs:
                        subs.remove(send_message)

    return Handler


def default_http_port() -> int:
    raw = os.environ.get("EMERGENCE_HTTP_PORT", str(_DEFAULT_PORT))
    return int(raw)
