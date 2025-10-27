from __future__ import annotations

from pacx.batch import parse_batch_response


def test_parse_batch_response_ok():
    boundary = "batchresponse_123"
    body = f"""--{boundary}
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: 1

HTTP/1.1 201 Created

{{"id": "1"}}
--{boundary}
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: 2

HTTP/1.1 400 Bad Request

{{"error": {{"message": "oops"}}}}
--{boundary}--
"""
    res = parse_batch_response(f"multipart/mixed; boundary={boundary}", body.encode("utf-8"))
    assert len(res) == 2
    assert res[0]["status_code"] == 201
    assert res[1]["status_code"] == 400


def test_parse_batch_response_with_quoted_boundary():
    boundary = "quoted_batch"
    body = f"""--{boundary}
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: 1

HTTP/1.1 200 OK

{{"result": "ok"}}
--{boundary}--
"""
    res = parse_batch_response(
        f'multipart/mixed; boundary="{boundary}"', body.encode("utf-8")
    )
    assert len(res) == 1
    assert res[0]["status_code"] == 200


def test_parse_batch_response_preserves_reason_phrase():
    boundary = "batch_hyphen_reason"
    body = f"""--{boundary}
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: 1

HTTP/1.1 207 Multi-Status

{{"result": "ok"}}
--{boundary}--
"""
    res = parse_batch_response(f"multipart/mixed; boundary={boundary}", body.encode("utf-8"))
    assert res[0]["reason"] == "Multi-Status"
