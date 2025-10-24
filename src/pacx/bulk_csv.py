from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .batch import BatchSendResult, send_batch
from .clients.dataverse import DataverseClient
from .odata import build_alternate_key_segment


@dataclass
class BulkCsvResult:
    operations: list[dict[str, Any]]
    stats: dict[str, Any]


def bulk_csv_upsert(
    dv: DataverseClient,
    entityset: str,
    csv_path: str,
    id_column: str,
    *,
    key_columns: list[str] | None = None,
    chunk_size: int = 50,
    create_if_missing: bool = True,
) -> list[dict[str, Any]]:
    """Upsert records from CSV using OData $batch.

    Returns per-operation results: list of dicts with content_id, status_code, reason, json, text.
    """
    rows: list[tuple[int, dict[str, Any]]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append((r.line_num, row))

    def chunk(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    all_results: list[dict[str, Any]] = []
    retry_histogram: Counter[int] = Counter()
    total_retries = 0
    grouped_errors: Counter[str] = Counter()
    total_attempts = 0
    for group in chunk(rows, chunk_size):
        ops: list[dict[str, Any]] = []
        op_row_numbers: list[int] = []
        for row_number, row in group:
            rid = row.get(id_column)
            body = {k: v for k, v in row.items() if k != id_column and v not in ("", None)}
            if rid:
                ops.append(
                    {"method": "PATCH", "url": f"/api/data/v9.2/{entityset}({rid})", "body": body}
                )
                op_row_numbers.append(row_number)
            elif key_columns and all(row.get(k) not in (None, "") for k in key_columns):
                key_map = {k: row[k] for k in key_columns}
                seg = build_alternate_key_segment(key_map)
                ops.append(
                    {"method": "PATCH", "url": f"/api/data/v9.2/{entityset}({seg})", "body": body}
                )
                op_row_numbers.append(row_number)
            elif create_if_missing:
                ops.append({"method": "POST", "url": f"/api/data/v9.2/{entityset}", "body": body})
                op_row_numbers.append(row_number)
        if ops:
            batch_res: BatchSendResult = send_batch(dv, ops)
            total_attempts = max(total_attempts, batch_res.attempts)
            for count in batch_res.retry_counts.values():
                retry_histogram[count] += 1
                total_retries += count
            for op_result in batch_res.operations:
                local_index = op_result.get("operation_index", 0)
                row_number = op_row_numbers[local_index]
                op_result["row_index"] = row_number
                status = int(op_result.get("status_code") or 0)
                if status < 200 or status >= 300:
                    grouped_errors[str(status or op_result.get("reason") or "unknown")] += 1
                all_results.append(op_result)

    successes = sum(1 for r in all_results if 200 <= int(r.get("status_code") or 0) < 300)
    failures = sum(1 for r in all_results if not (200 <= int(r.get("status_code") or 0) < 300))
    stats = {
        "total_rows": len(rows),
        "attempts": total_attempts,
        "successes": successes,
        "failures": failures,
        "retry_invocations": total_retries,
        "retry_histogram": dict(retry_histogram),
        "grouped_errors": dict(grouped_errors),
    }
    return BulkCsvResult(operations=all_results, stats=stats)
