
from __future__ import annotations

import re
from typing import List, Dict, Any, Tuple, Optional

from .clients.dataverse import DataverseClient


def _encode_part(headers: Dict[str, str], body: str) -> str:
    lines = []
    for k, v in headers.items():
        lines.append(f"{k}: {v}")
    lines.append("")  # header/body separator
    lines.append(body)
    return "\r\n".join(lines)


def build_batch(ops: List[Dict[str, Any]]) -> Tuple[str, bytes]:
    """Build a multipart/mixed OData $batch request body.

    Each op: {"method": "PATCH|POST|DELETE|GET", "url": "/api/data/v9.2/ENTITYSET(...)", "body": dict|None}
    URLs should be relative to the Dataverse base (no scheme/host) but can include the api path.
    """
    import uuid, json
    batch_id = f"batch_{uuid.uuid4()}"
    changeset_id = f"changeset_{uuid.uuid4()}"
    batch_lines: List[str] = []

    batch_lines.append(f"--{batch_id}")
    batch_lines.append(f"Content-Type: multipart/mixed; boundary={changeset_id}")
    batch_lines.append("")
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
        part = _encode_part(cs_headers, "\r\n".join(req_lines))
        batch_lines.append(part)
        batch_lines.append("")
    batch_lines.append(f"--{changeset_id}--")
    batch_lines.append("")
    batch_lines.append(f"--{batch_id}--")
    batch_lines.append("")

    body_bytes = "\r\n".join(batch_lines).encode("utf-8")
    return batch_id, body_bytes


def parse_batch_response(content_type: str, body: bytes) -> List[Dict[str, Any]]:
    """Parse a Dataverse $batch multipart/mixed response into a list of per-op results.

    Returns: [{content_id, status_code, reason, json, text}]
    """
    m = re.search(r'boundary=([\w\-\_\.]+)', content_type or "", re.IGNORECASE)
    if not m:
        return [{"status_code": 0, "reason": "NoBoundary", "text": body.decode(errors="replace")}]
    boundary = m.group(1)
    raw = body.decode("utf-8", errors="replace")
    parts = [p for p in raw.split(f"--{boundary}") if p.strip() and p.strip() != "--"]
    results: List[Dict[str, Any]] = []
    for part in parts:
        # Expect nested application/http blocks with Content-ID
        cid_m = re.search(r"Content-ID:\s*(\d+)", part, re.IGNORECASE)
        content_id = int(cid_m.group(1)) if cid_m else None
        # Status line like: HTTP/1.1 201 Created
        status_m = re.search(r"HTTP/\d\.\d\s+(\d{3})\s+([\w\s]+)", part)
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
        except Exception:
            pass
        results.append({"content_id": content_id, "status_code": scode, "reason": reason, "json": j, "text": text})
    return results


def send_batch(dv: DataverseClient, ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    batch_id, body = build_batch(ops)
    headers = {"Content-Type": f'multipart/mixed; boundary={batch_id}'}
    resp = dv.http.post("$batch", headers=headers, data=body)
    return parse_batch_response(resp.headers.get("Content-Type", ""), resp.content)
