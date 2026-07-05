"""Integration tests for HTTP ingress (M25)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from emergence.kernel.runtime import RuntimeService
from tests.helpers_admin import short_data_dir


def _http_json(url: str, *, method: str = "GET", body: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


@pytest.mark.integration
class TestHttpIntegration:
    def test_create_goal_and_fetch_timeline(self, monkeypatch):
        data_dir = short_data_dir("http-goals")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_HTTP_PORT", "0")

        service = RuntimeService.start()
        try:
            base = service.http.base_url()
            created = _http_json(
                f"{base}/goals",
                method="POST",
                body={"description": "HTTP research topic", "mode": "goal"},
            )
            goal_id = created["goal_id"]
            assert created["tracking_url"].endswith(goal_id)

            goal = _http_json(f"{base}/goals/{goal_id}")
            assert goal["description"] == "HTTP research topic"

            timeline = _http_json(f"{base}/goals/{goal_id}/timeline")
            assert isinstance(timeline["groups"], list)

            snapshot = _http_json(f"{base}/system/snapshot")
            assert "processes" in snapshot
        finally:
            service.stop()

    def test_event_inspect_endpoint(self, monkeypatch):
        data_dir = short_data_dir("http-inspect")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_HTTP_PORT", "0")

        service = RuntimeService.start()
        try:
            base = service.http.base_url()
            created = _http_json(
                f"{base}/goals",
                method="POST",
                body={"description": "Inspect flow", "mode": "goal"},
            )
            timeline = _http_json(f"{base}/goals/{created['goal_id']}/timeline")
            event_id = timeline["groups"][0]["entries"][0]["event_id"]
            inspected = _http_json(f"{base}/events/{event_id}/inspect")
            assert inspected["event_id"] == event_id
            assert inspected["narrative"]
        finally:
            service.stop()

    def test_channel_webhook_creates_goal(self, monkeypatch):
        data_dir = short_data_dir("http-channel")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_HTTP_PORT", "0")

        service = RuntimeService.start()
        try:
            base = service.http.base_url()
            created = _http_json(
                f"{base}/channels/webhook",
                method="POST",
                body={"text": "Research HTTP channels"},
            )
            assert "tracking_url" in created
            assert created["goal_id"]
        finally:
            service.stop()

    def test_auth_rejects_without_token(self, monkeypatch):
        data_dir = short_data_dir("http-auth")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_HTTP_PORT", "0")
        monkeypatch.setenv("EMERGENCE_API_TOKEN", "secret-token")

        service = RuntimeService.start()
        try:
            base = service.http.base_url()
            with pytest.raises(urllib.error.HTTPError) as exc:
                _http_json(f"{base}/health")
            assert exc.value.code == 401
        finally:
            service.stop()
            monkeypatch.delenv("EMERGENCE_API_TOKEN", raising=False)
