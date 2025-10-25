from __future__ import annotations

import csv

import httpx

from pacx.bulk_csv import bulk_csv_upsert
from pacx.clients.dataverse import DataverseClient


def test_bulk_csv_altkey_patch(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    csvp = tmp_path / "data.csv"
    with open(csvp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["accountnumber", "name", "city"])
        w.writerow(["A/1", "Co-op/O'Connor", "Seattle"])  # no id column present; use keys

    # Intercept $batch and assert the alt-key URL appears
    def callback(request):
        body = request.content.decode("utf-8", errors="replace")
        expected = "".join(
            [
                "PATCH /api/data/v9.2/accounts(accountnumber='A%2F1',",
                "name='Co-op%2FO%27%27Connor') HTTP/1.1",
            ]
        )
        assert expected in body
        response_body = """--batchresponse_1
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: 1

HTTP/1.1 204 No Content


--batchresponse_1--
"""
        return httpx.Response(
            200,
            headers={"Content-Type": "multipart/mixed; boundary=batchresponse_1"},
            content=response_body.encode("utf-8"),
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/$batch").mock(
        side_effect=callback
    )

    res = bulk_csv_upsert(
        dv,
        "accounts",
        str(csvp),
        id_column="id",
        key_columns=["accountnumber", "name"],
        chunk_size=10,
    )
    assert res.operations
