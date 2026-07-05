"""
Unit tests for admin protocol encoding/decoding.
"""

from __future__ import annotations

import pytest

from emergence.admin.protocol import (
    AdminResponse,
    ProtocolError,
    decode_response_line,
    encode_request,
)


@pytest.mark.unit
class TestAdminProtocol:
    def test_encode_request_includes_method_and_params(self):
        raw = encode_request(
            "snapshot",
            params={"wide": True},
            request_id="42",
        )
        assert b'"method": "snapshot"' in raw
        assert b'"id": "42"' in raw
        assert raw.endswith(b"\n")

    def test_decode_response_success(self):
        response = decode_response_line(
            b'{"id":"1","ok":true,"result":{"status":"ok"}}\n'
        )
        assert response.ok is True
        assert response.result == {"status": "ok"}

    def test_decode_response_error(self):
        response = decode_response_line(
            b'{"id":"1","ok":false,"error":"nope"}\n'
        )
        assert response.ok is False
        assert response.error == "nope"

    def test_decode_invalid_json_raises(self):
        with pytest.raises(ProtocolError):
            decode_response_line(b"not-json")

    def test_admin_response_round_trip(self):
        response = AdminResponse(
            request_id="9",
            ok=True,
            result={"count": 3},
        )
        decoded = AdminResponse.from_json(response.to_json())
        assert decoded.request_id == "9"
        assert decoded.result == {"count": 3}
