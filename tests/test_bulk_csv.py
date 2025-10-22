
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
    bulk_csv_upsert(dv, "accounts", str(csvp), id_column="id", chunk_size=2)
