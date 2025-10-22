
from __future__ import annotations

import csv
from pathlib import Path

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.bulk_csv import bulk_csv_upsert


def test_bulk_csv_posts_batch(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id","name"])
        w.writerow(["123","A"])
        w.writerow(["","B"])

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        return_value=httpx.Response(202)
    )
    result = bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=2)
    assert result.stats["total_rows"] == 2


def test_bulk_csv_reports_retries(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id","name"])
        w.writerow(["","Retry"])

    calls = []

    def responder(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        boundary = "batchresponse_test"
        if len(calls) == 1:
            body = f"--{boundary}\nContent-Type: application/http\nContent-Transfer-Encoding: binary\nContent-ID: 1\n\nHTTP/1.1 429 Too Many Requests\n\n{{}}\n--{boundary}--"
        else:
            body = f"--{boundary}\nContent-Type: application/http\nContent-Transfer-Encoding: binary\nContent-ID: 1\n\nHTTP/1.1 204 No Content\n\n\n--{boundary}--"
        return httpx.Response(200, headers={"Content-Type": f"multipart/mixed; boundary={boundary}"}, content=body.encode("utf-8"))

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(side_effect=responder)

    result = bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=1)
    assert result.stats["retry_invocations"] == 1
