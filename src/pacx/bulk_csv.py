
from __future__ import annotations

import csv
from typing import List, Dict, Any, Optional

from .clients.dataverse import DataverseClient
from .batch import send_batch
from .odata import build_alternate_key_segment


def bulk_csv_upsert(
    dv: DataverseClient,
    entityset: str,
    csv_path: str,
    id_column: str,
    *,
    key_columns: list[str] | None = None,
    chunk_size: int = 50,
    create_if_missing: bool = True,
) -> List[Dict[str, Any]]:
    """Upsert records from CSV using OData $batch.

    Returns per-operation results: list of dicts with content_id, status_code, reason, json, text.
    """
    rows: List[Dict[str, Any]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)

    def chunk(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    all_results: List[Dict[str, Any]] = []
    for group in chunk(rows, chunk_size):
        ops: List[Dict[str, Any]] = []
        for idx, row in enumerate(group, start=1):
            rid = row.get(id_column)
            body = {k: v for k, v in row.items() if k != id_column and v not in ("", None)}
            if rid:
                ops.append({"method": "PATCH", "url": f"/api/data/v9.2/{entityset}({rid})", "body": body})
            elif key_columns and all(row.get(k) not in (None, "") for k in key_columns):
                key_map = {k: row[k] for k in key_columns}
                seg = build_alternate_key_segment(key_map)
                ops.append({"method": "PATCH", "url": f"/api/data/v9.2/{entityset}({seg})", "body": body})
            elif create_if_missing:
                ops.append({"method": "POST", "url": f"/api/data/v9.2/{entityset}", "body": body})
        if ops:
            res = send_batch(dv, ops)
            # annotate with local row offset
            for i, item in enumerate(res, start=1):
                item["row_index"] = i  # within this chunk
            all_results.extend(res)
    return all_results
