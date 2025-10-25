from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .batch import BatchSendResult, send_batch
from .clients.dataverse import DataverseClient
from .odata import build_alternate_key_segment
from .utils.guid import sanitize_guid


@dataclass
class BulkCsvOperationResult:
    """Outcome for a single CSV row processed through the bulk upsert helper."""

    row_index: int | None
    content_id: int | None
    status_code: int
    reason: str
    json: object | None
    text: str | None
    operation_index: int | None = None

    @classmethod
    def from_batch_result(
        cls,
        payload: dict[str, object],
        *,
        row_index: int | None,
    ) -> "BulkCsvOperationResult":
        """Build a :class:`BulkCsvOperationResult` from a batch response entry."""

        content_id = payload.get("content_id")
        operation_index = payload.get("operation_index")
        status_code_raw = payload.get("status_code")
        reason = payload.get("reason")
        if isinstance(content_id, str) and content_id.isdigit():
            content_id_value: int | None = int(content_id)
        elif isinstance(content_id, int):
            content_id_value = content_id
        else:
            content_id_value = None
        if isinstance(status_code_raw, str) and status_code_raw.isdigit():
            status_code_value = int(status_code_raw)
        elif isinstance(status_code_raw, int):
            status_code_value = status_code_raw
        else:
            status_code_value = 0
        if isinstance(operation_index, str) and operation_index.isdigit():
            operation_index_value: int | None = int(operation_index)
        elif isinstance(operation_index, int):
            operation_index_value = operation_index
        else:
            operation_index_value = None
        return cls(
            row_index=row_index,
            content_id=content_id_value,
            status_code=status_code_value,
            reason=str(reason) if reason is not None else "Unknown",
            json=payload.get("json"),
            text=str(payload.get("text")) if payload.get("text") is not None else None,
            operation_index=operation_index_value,
        )


@dataclass
class BulkCsvStats:
    """Aggregate statistics returned by :func:`bulk_csv_upsert`."""

    total_rows: int
    attempts: int
    successes: int
    failures: int
    retry_invocations: int
    retry_histogram: dict[int, int]
    grouped_errors: dict[str, int]


@dataclass
class BulkCsvResult:
    """Typed return structure for :func:`bulk_csv_upsert`."""

    operations: list[BulkCsvOperationResult]
    stats: BulkCsvStats


def bulk_csv_upsert(
    dv: DataverseClient,
    entityset: str,
    csv_path: str,
    id_column: str,
    *,
    key_columns: list[str] | None = None,
    chunk_size: int = 50,
    create_if_missing: bool = True,
) -> BulkCsvResult:
    """Upsert records from CSV using OData $batch.

    Args:
        dv: Authenticated Dataverse client.
        entityset: Logical table name to target.
        csv_path: Path to the CSV file containing data to upsert.
        id_column: Column containing record identifiers for PATCH.
        key_columns: Alternate key columns used when ``id_column`` is blank.
        chunk_size: Number of rows per $batch request.
        create_if_missing: When ``True`` missing rows will be created.

    Returns:
        :class:`BulkCsvResult` containing per-row outcomes and aggregate statistics.

    Example:
        >>> result = bulk_csv_upsert(client, "accounts", "rows.csv", "accountid")
        >>> result.stats.successes
        42
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1 to process CSV rows")

    rows: list[tuple[int, dict[str, Any]]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append((r.line_num, row))

    def chunk(
        lst: list[tuple[int, dict[str, Any]]], n: int
    ) -> Iterable[list[tuple[int, dict[str, Any]]]]:
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    all_results: list[BulkCsvOperationResult] = []
    retry_histogram: Counter[int] = Counter()
    total_retries = 0
    grouped_errors: Counter[str] = Counter()
    total_attempts = 0
    for group in chunk(rows, chunk_size):
        ops: list[dict[str, Any]] = []
        op_row_numbers: list[int] = []
        for row_number, row in group:
            rid_raw = row.get(id_column)
            rid: str | None
            if isinstance(rid_raw, str):
                rid = sanitize_guid(rid_raw)
            elif rid_raw is None:
                rid = None
            else:
                rid = str(rid_raw)
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
                local_index_raw = op_result.get("operation_index")
                if isinstance(local_index_raw, str) and local_index_raw.isdigit():
                    local_index = int(local_index_raw)
                elif isinstance(local_index_raw, int):
                    local_index = local_index_raw
                else:
                    local_index = 0
                result_row_index = (
                    op_row_numbers[local_index] if local_index < len(op_row_numbers) else None
                )
                enriched = BulkCsvOperationResult.from_batch_result(
                    op_result, row_index=result_row_index
                )
                status = enriched.status_code
                if status < 200 or status >= 300:
                    grouped_errors[str(status or enriched.reason or "unknown")] += 1
                all_results.append(enriched)

    successes = sum(1 for r in all_results if 200 <= r.status_code < 300)
    failures = sum(1 for r in all_results if not (200 <= r.status_code < 300))
    stats = BulkCsvStats(
        total_rows=len(rows),
        attempts=total_attempts,
        successes=successes,
        failures=failures,
        retry_invocations=total_retries,
        retry_histogram=dict(retry_histogram),
        grouped_errors=dict(grouped_errors),
    )
    return BulkCsvResult(operations=all_results, stats=stats)


__all__ = [
    "BulkCsvOperationResult",
    "BulkCsvStats",
    "BulkCsvResult",
    "bulk_csv_upsert",
]
