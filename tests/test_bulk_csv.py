from __future__ import annotations

import csv
import types

import pytest

import httpx

from pacx.batch import BatchSendResult
from pacx.bulk_csv import bulk_csv_upsert
from pacx.clients.dataverse import DataverseClient


def test_bulk_csv_posts_batch(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name"])
        w.writerow(["123", "A"])
        w.writerow(["", "B"])

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        return_value=httpx.Response(202)
    )
    result = bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=2)
    assert result.stats.total_rows == 2


def test_bulk_csv_rejects_chunk_size_under_one(tmp_path, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name"])
        writer.writerow(["123", "Alpha"])

    with pytest.raises(ValueError, match="chunk_size must be at least 1"):
        bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=0)


def test_bulk_csv_reports_retries(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name"])
        w.writerow(["", "Retry"])

    calls = []

    def responder(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        boundary = "batchresponse_test"
        if len(calls) == 1:
            body = f"--{boundary}\nContent-Type: application/http\nContent-Transfer-Encoding: binary\nContent-ID: 1\n\nHTTP/1.1 429 Too Many Requests\n\n{{}}\n--{boundary}--"
        else:
            body = f"--{boundary}\nContent-Type: application/http\nContent-Transfer-Encoding: binary\nContent-ID: 1\n\nHTTP/1.1 204 No Content\n\n\n--{boundary}--"
        return httpx.Response(
            200,
            headers={"Content-Type": f"multipart/mixed; boundary={boundary}"},
            content=body.encode("utf-8"),
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        side_effect=responder
    )

    result = bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=1)
    assert result.stats.retry_invocations == 1


def test_bulk_csv_row_index_matches_csv_line_with_skipped_rows(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name"])
        w.writerow(["", "Skipped"])
        w.writerow(["42", "Valid"])

    boundary = "batchresponse_rowindex"
    body = (
        f"--{boundary}\n"
        "Content-Type: application/http\n"
        "Content-Transfer-Encoding: binary\n"
        "Content-ID: 1\n\n"
        "HTTP/1.1 204 No Content\n\n\n"
        f"--{boundary}--"
    )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        return_value=httpx.Response(
            200,
            headers={"Content-Type": f"multipart/mixed; boundary={boundary}"},
            content=body.encode("utf-8"),
        )
    )

    result = bulk_csv_upsert(
        dv,
        "accounts",
        str(csvp),
        id_column="id",
        chunk_size=10,
        create_if_missing=False,
    )

    assert len(result.operations) == 1
    assert result.operations[0].row_index == 3


def test_bulk_csv_sanitizes_ids_before_batch(monkeypatch, tmp_path, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name"])
        writer.writerow([" {ABC} ", "Alpha"])

    captured_ops: list[dict[str, object]] | None = None

    def fake_send_batch(dv_arg, ops):
        nonlocal captured_ops
        captured_ops = ops
        return types.SimpleNamespace(operations=[], retry_counts={}, attempts=1)

    monkeypatch.setattr("pacx.bulk_csv.send_batch", fake_send_batch)

    bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=1)

    assert captured_ops is not None
    assert captured_ops[0]["url"].endswith("accounts(ABC)")


def test_bulk_csv_aggregates_attempts_across_chunks(monkeypatch, tmp_path, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name"])
        writer.writerow(["1", "First"])
        writer.writerow(["2", "Second"])

    responses = [
        BatchSendResult(
            operations=[{"status_code": 204, "operation_index": 0}],
            retry_counts={0: 1},
            attempts=2,
        ),
        BatchSendResult(
            operations=[{"status_code": 204, "operation_index": 0}],
            retry_counts={},
            attempts=3,
        ),
    ]
    call_index = 0

    def fake_send_batch(dv_arg, ops):
        nonlocal call_index
        assert dv_arg is dv
        assert call_index < len(responses)
        response = responses[call_index]
        call_index += 1
        return response

    monkeypatch.setattr("pacx.bulk_csv.send_batch", fake_send_batch)

    result = bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=1)

    assert call_index == 2
    assert result.stats.total_rows == 2
    assert result.stats.attempts == sum(r.attempts for r in responses)
    assert result.stats.retry_invocations == 1
