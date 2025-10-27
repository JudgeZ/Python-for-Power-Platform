from __future__ import annotations

import re

import httpx
import respx

from pacx.batch import send_batch
from pacx.clients.dataverse import DataverseClient


def _build_body(statuses: list[int]) -> bytes:
    return _build_body_with_pairs([(i, status) for i, status in enumerate(statuses, start=1)])


def _build_body_with_pairs(pairs: list[tuple[int, int]]) -> bytes:
    boundary = "batchresponse_test"
    segments = []
    for content_id, status in pairs:
        reason = "OK" if status < 400 else "Error"
        payload = "{}"
        segments.append(
            f"--{boundary}\nContent-Type: application/http\nContent-Transfer-Encoding: binary\nContent-ID: {content_id}\n\nHTTP/1.1 {status} {reason}\n\n{payload}"
        )
    segments.append(f"--{boundary}--")
    return "\n".join(segments).encode("utf-8")


def test_send_batch_retries_transient(respx_mock: respx.Router, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    calls: list[int] = []

    def responder(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(
                200,
                headers={"Content-Type": "multipart/mixed; boundary=batchresponse_test"},
                content=_build_body([429]),
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "multipart/mixed; boundary=batchresponse_test"},
            content=_build_body([204]),
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        side_effect=responder
    )

    result = send_batch(
        dv,
        [{"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {}}],
        base_backoff=0.0,
    )

    assert result.retry_counts[0] == 1
    assert result.operations[0]["status_code"] == 204


def test_send_batch_handles_missing_responses(respx_mock: respx.Router, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "multipart/mixed; boundary=batchresponse_test"},
            content=_build_body([204]),
        )
    )

    result = send_batch(
        dv,
        [
            {"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {}},
            {"method": "PATCH", "url": "/api/data/v9.2/accounts(2)", "body": {}},
        ],
        base_backoff=0.0,
    )

    assert len(result.operations) == 2
    assert result.operations[0]["operation_index"] == 0
    assert result.operations[0]["status_code"] == 204
    assert result.operations[1]["operation_index"] == 1
    assert result.operations[1]["status_code"] == 0
    assert result.operations[1]["reason"] == "MissingResponse"


def test_send_batch_mixed_read_and_write(respx_mock: respx.Router, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")

    def responder(request: httpx.Request) -> httpx.Response:
        content_type = request.headers["Content-Type"]
        match = re.search(r"boundary=([^;]+)", content_type)
        assert match is not None
        boundary = match.group(1)
        raw = request.content.decode("utf-8")
        assert raw.startswith(f"--{boundary}")
        assert raw.strip().endswith(f"--{boundary}--")

        segments = [
            part.strip()
            for part in raw.split(f"--{boundary}")
            if part.strip() and part.strip() != "--"
        ]
        assert len(segments) == 2

        first_part, second_part = segments
        assert "Content-Type: application/http" in first_part
        assert first_part.startswith("Content-Type: application/http")
        assert "GET /api/data/v9.2/accounts?$top=1 HTTP/1.1" in first_part
        assert "multipart/mixed" not in first_part
        assert "Content-ID: 1" in first_part

        assert "Content-Type: multipart/mixed; boundary=changeset_" in second_part
        assert second_part.count("--changeset_") >= 2
        assert "PATCH /api/data/v9.2/accounts(1) HTTP/1.1" in second_part
        assert "Content-ID: 2" in second_part
        nested_boundary_match = re.search(r"boundary=(changeset_[^;\s]+)", second_part)
        assert nested_boundary_match is not None
        nested_boundary = nested_boundary_match.group(1)
        request_chunks = [
            chunk.strip()
            for chunk in second_part.split(f"--{nested_boundary}")
            if chunk.strip().startswith("Content-Type: application/http")
        ]
        assert len(request_chunks) == 1
        for chunk in request_chunks:
            assert chunk.startswith("Content-Type: application/http")
        assert second_part.strip().endswith(f"--{nested_boundary}--")

        return httpx.Response(
            200,
            headers={"Content-Type": "multipart/mixed; boundary=batchresponse_test"},
            content=_build_body([200, 204]),
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        side_effect=responder
    )

    result = send_batch(
        dv,
        [
            {"method": "GET", "url": "/api/data/v9.2/accounts?$top=1", "body": None},
            {"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {"name": "Updated"}},
        ],
        base_backoff=0.0,
    )

    assert len(result.operations) == 2
    assert result.operations[0]["status_code"] == 200
    assert result.operations[1]["status_code"] == 204


def test_send_batch_reconciles_out_of_order_response(
    respx_mock: respx.Router, token_getter
):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": "multipart/mixed; boundary=batchresponse_test"},
            content=_build_body_with_pairs([(2, 204), (1, 400)]),
        )
    )

    result = send_batch(
        dv,
        [
            {"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {}},
            {"method": "PATCH", "url": "/api/data/v9.2/accounts(2)", "body": {}},
        ],
        base_backoff=0.0,
        max_retries=0,
    )

    assert len(result.operations) == 2
    assert result.operations[0]["operation_index"] == 0
    assert result.operations[0]["status_code"] == 400
    assert result.operations[1]["operation_index"] == 1
    assert result.operations[1]["status_code"] == 204
