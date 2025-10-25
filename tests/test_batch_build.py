from __future__ import annotations

import httpx
import respx

from pacx.batch import build_batch, send_batch
from pacx.clients.dataverse import DataverseClient


def _split_batch_parts(body: str, boundary: str) -> list[str]:
    parts: list[str] = []
    for raw_part in body.split(f"--{boundary}"):
        stripped = raw_part.strip()
        if not stripped or stripped == "--":
            continue
        parts.append(stripped)
    return parts


def _build_response_body(statuses: list[int]) -> bytes:
    boundary = "batchresponse_mixed"
    segments: list[str] = []
    for idx, status in enumerate(statuses, start=1):
        reason = "OK" if status < 400 else "Error"
        segments.append(
            "\r\n".join(
                [
                    f"--{boundary}",
                    "Content-Type: application/http",
                    "Content-Transfer-Encoding: binary",
                    f"Content-ID: {idx}",
                    "",
                    f"HTTP/1.1 {status} {reason}",
                    "",
                    "{}",
                ]
            )
        )
    segments.append(f"--{boundary}--")
    return "\r\n".join(segments).encode("utf-8")


def test_build_batch_places_get_operations_outside_changesets() -> None:
    ops = [
        {"method": "GET", "url": "/api/data/v9.2/accounts?$top=1", "body": None},
        {"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {"name": "Updated"}},
        {"method": "GET", "url": "/api/data/v9.2/contacts?$top=1", "body": None},
        {"method": "POST", "url": "/api/data/v9.2/leads", "body": {"subject": "New"}},
    ]

    batch_id, payload = build_batch(ops)
    text = payload.decode("utf-8")
    parts = _split_batch_parts(text, batch_id)

    assert parts[0].startswith("Content-Type: application/http")
    assert "GET /api/data/v9.2/accounts?$top=1 HTTP/1.1" in parts[0]

    assert parts[1].startswith("Content-Type: multipart/mixed; boundary=")
    assert "PATCH /api/data/v9.2/accounts(1) HTTP/1.1" in parts[1]
    assert "GET" not in parts[1]

    assert parts[2].startswith("Content-Type: application/http")
    assert "GET /api/data/v9.2/contacts?$top=1 HTTP/1.1" in parts[2]

    assert parts[3].startswith("Content-Type: multipart/mixed; boundary=")
    assert "POST /api/data/v9.2/leads HTTP/1.1" in parts[3]

    for part in parts:
        if part.startswith("Content-Type: application/http"):
            assert "--changeset" not in part


def test_send_batch_with_mixed_operations_uses_expected_layout(
    respx_mock: respx.Router, token_getter
) -> None:
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    captured: dict[str, str] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["content_type"] = request.headers["Content-Type"]
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            headers={"Content-Type": "multipart/mixed; boundary=batchresponse_mixed"},
            content=_build_response_body([200, 204, 201]),
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        side_effect=responder
    )

    ops = [
        {"method": "GET", "url": "/api/data/v9.2/accounts?$top=1", "body": None},
        {"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {"name": "Updated"}},
        {"method": "POST", "url": "/api/data/v9.2/leads", "body": {"subject": "New"}},
    ]

    result = send_batch(dv, ops, base_backoff=0.0)

    assert result.operations[0]["status_code"] == 200
    assert result.operations[1]["status_code"] == 204
    assert result.operations[2]["status_code"] == 201

    boundary = captured["content_type"].split("boundary=")[1]
    parts = _split_batch_parts(captured["body"], boundary)

    assert parts[0].startswith("Content-Type: application/http")
    assert "GET /api/data/v9.2/accounts?$top=1 HTTP/1.1" in parts[0]

    assert parts[1].startswith("Content-Type: multipart/mixed; boundary=")
    assert "PATCH /api/data/v9.2/accounts(1) HTTP/1.1" in parts[1]
    assert "POST /api/data/v9.2/leads HTTP/1.1" in parts[1]
    assert "GET" not in parts[1]

