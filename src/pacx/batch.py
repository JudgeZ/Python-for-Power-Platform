from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from email.parser import HeaderParser
from typing import Any

from .clients.dataverse import DataverseClient

logger = logging.getLogger(__name__)


def _encode_part(headers: dict[str, str], body: str) -> str:
    lines = []
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    lines.append("")  # header/body separator
    lines.append(body)
    return "\r\n".join(lines)


def build_batch(ops: list[dict[str, Any]]) -> tuple[str, bytes]:
    """Build a multipart/mixed OData $batch request body.

    Each op: {"method": "PATCH|POST|DELETE|GET", "url": "/api/data/v9.2/ENTITYSET(...)", "body": dict|None}
    URLs should be relative to the Dataverse base (no scheme/host) but can include the api path.
    """
    import json
    import uuid

    batch_id = f"batch_{uuid.uuid4()}"
    batch_lines: list[str] = []
    pending_writes: list[tuple[dict[str, str], str]] = []

    def flush_writes() -> None:
        if not pending_writes:
            return
        changeset_id = f"changeset_{uuid.uuid4()}"
        batch_lines.extend(
            [
                f"--{batch_id}",
                f"Content-Type: multipart/mixed; boundary={changeset_id}",
                "",
            ]
        )
        for headers, request_text in pending_writes:
            batch_lines.append(f"--{changeset_id}")
            batch_lines.append(_encode_part(headers, request_text))
            batch_lines.append("")
        batch_lines.extend([f"--{changeset_id}--", ""])
        pending_writes.clear()

    for i, op in enumerate(ops, start=1):
        body = op.get("body")
        method = op["method"].upper()
        url = op["url"]
        cs_headers = {
            "Content-Type": "application/http",
            "Content-Transfer-Encoding": "binary",
            "Content-ID": str(i),
        }
        req_lines = [f"{method} {url} HTTP/1.1", "Content-Type: application/json; charset=utf-8"]
        req_lines.append("")
        req_lines.append(json.dumps(body) if body is not None else "")
        request_text = "\r\n".join(req_lines)
        if method == "GET":
            flush_writes()
            batch_lines.append(f"--{batch_id}")
            batch_lines.append(_encode_part(cs_headers, request_text))
            batch_lines.append("")
        else:
            pending_writes.append((cs_headers, request_text))

    flush_writes()
    batch_lines.append(f"--{batch_id}--")
    batch_lines.append("")

    body_bytes = "\r\n".join(batch_lines).encode("utf-8")
    return batch_id, body_bytes


def parse_batch_response(content_type: str, body: bytes) -> list[dict[str, Any]]:
    """Parse a Dataverse $batch multipart/mixed response into a list of per-op results.

    Returns: [{content_id, status_code, reason, json, text}]
    """
    boundary: str | None = None
    if content_type:
        try:
            parser = HeaderParser()
            headers = parser.parsestr(f"Content-Type: {content_type}", headersonly=True)
            raw_boundary = headers.get_param("boundary", header="content-type")
            if isinstance(raw_boundary, tuple):
                boundary = next(
                    (part for part in raw_boundary if isinstance(part, str) and part),
                    None,
                )
            elif isinstance(raw_boundary, str):
                boundary = raw_boundary
        except Exception:  # pragma: no cover - defensive fallback to regex parsing
            logger.debug("Failed to parse Content-Type header for boundary", exc_info=True)
    if not boundary:
        # Fall back to simple regex for legacy or malformed headers.
        m = re.search(r"boundary=([\w\-\_\.]+)", content_type or "", re.IGNORECASE)
        if m:
            boundary = m.group(1)
    if not boundary:
        return [{"status_code": 0, "reason": "NoBoundary", "text": body.decode(errors="replace")}]
    raw = body.decode("utf-8", errors="replace")
    parts = [p for p in raw.split(f"--{boundary}") if p.strip() and p.strip() != "--"]
    results: list[dict[str, Any]] = []
    for part in parts:
        # Expect nested application/http blocks with Content-ID
        cid_m = re.search(r"Content-ID:\s*(\d+)", part, re.IGNORECASE)
        content_id = int(cid_m.group(1)) if cid_m else None
        # Status line like: HTTP/1.1 201 Created
        status_m = re.search(r"HTTP/\d\.\d\s+(\d{3})\s+([^\r\n]+)", part)
        scode = int(status_m.group(1)) if status_m else 0
        reason = status_m.group(2).strip() if status_m else "Unknown"
        # Body (after blank line following status/headers)
        body_m = re.split(r"\r?\n\r?\n", part, maxsplit=1)
        text = body_m[1] if len(body_m) > 1 else ""
        # Try JSON parse
        j = None
        try:
            import json as _json

            j = _json.loads(text) if text.strip() else None
        except Exception:  # pragma: no cover - defensive best-effort parse
            logger.debug("Failed to parse batch response part as JSON", exc_info=True)
        results.append(
            {
                "content_id": content_id,
                "status_code": scode,
                "reason": reason,
                "json": j,
                "text": text,
            }
        )
    return results


@dataclass
class BatchSendResult:
    operations: list[dict[str, Any]]
    retry_counts: dict[int, int]
    attempts: int


TRANSIENT_STATUSES = {429, 500, 502, 503, 504}


def send_batch(
    dv: DataverseClient,
    ops: list[dict[str, Any]],
    *,
    max_retries: int = 3,
    retry_statuses: set[int] | None = None,
    base_backoff: float = 0.5,
) -> BatchSendResult:
    statuses = retry_statuses or TRANSIENT_STATUSES
    pending = list(enumerate(ops))
    retry_counts: dict[int, int] = {}
    final_results: dict[int, dict[str, Any]] = {}
    attempt = 0

    while pending and attempt <= max_retries:
        attempt += 1
        idxs, payload = zip(*pending, strict=False)
        req_ops = list(payload)
        batch_id, body = build_batch(req_ops)
        headers = {"Content-Type": f"multipart/mixed; boundary={batch_id}"}
        resp = dv.http.post("$batch", headers=headers, content=body)
        parsed = parse_batch_response(resp.headers.get("Content-Type", ""), resp.content)

        next_round: list[tuple[int, dict[str, Any]]] = []
        pending_indices = list(idxs)
        position_lookup = {pos: idx for pos, idx in enumerate(pending_indices, start=1)}
        available_indices = pending_indices.copy()
        resolved: dict[int, dict[str, Any]] = {}

        # Dataverse can emit batch responses out of order. Reconcile each part
        # with its originating operation by Content-ID, falling back to the
        # response order when the header is missing.
        for result in parsed:
            cid = result.get("content_id")
            target_idx = position_lookup.get(cid) if cid is not None else None
            if target_idx is not None and target_idx in resolved:
                target_idx = None
            if target_idx is None:
                while available_indices and available_indices[0] in resolved:
                    available_indices.pop(0)
                if available_indices:
                    target_idx = available_indices.pop(0)
            if target_idx is None:
                continue
            if target_idx in available_indices:
                available_indices.remove(target_idx)
            resolved[target_idx] = result

        for idx in pending_indices:
            matched = resolved.get(idx)
            if matched is None:
                if idx not in final_results:
                    final_results[idx] = {
                        "status_code": 0,
                        "reason": "MissingResponse",
                        "operation_index": idx,
                    }
                continue
            matched["operation_index"] = idx
            if matched.get("status_code") in statuses and attempt <= max_retries:
                retry_counts[idx] = retry_counts.get(idx, 0) + 1
                next_round.append((idx, ops[idx]))
            else:
                final_results[idx] = matched
        if next_round and attempt <= max_retries:
            time.sleep(base_backoff * (2 ** (attempt - 1)))
        pending = next_round

    # attach final attempt results for any exhausted retries
    for idx, _ in pending:
        if idx not in final_results:
            final_results[idx] = {
                "status_code": 0,
                "reason": "RetryExhausted",
                "operation_index": idx,
            }

    ordered = [final_results[i] for i in sorted(final_results.keys())]
    return BatchSendResult(operations=ordered, retry_counts=retry_counts, attempts=attempt)
