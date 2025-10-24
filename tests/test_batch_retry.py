from __future__ import annotations

import httpx
import respx

from pacx.batch import send_batch
from pacx.clients.dataverse import DataverseClient


def _build_body(statuses: list[int]) -> bytes:
    boundary = "batchresponse_test"
    segments = []
    for i, status in enumerate(statuses, start=1):
        reason = "OK" if status < 400 else "Error"
        payload = "{}"
        segments.append(
            f"--{boundary}\nContent-Type: application/http\nContent-Transfer-Encoding: binary\nContent-ID: {i}\n\nHTTP/1.1 {status} {reason}\n\n{payload}"
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
