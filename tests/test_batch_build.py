from __future__ import annotations

import re

from pacx.batch import build_batch


def test_build_batch_includes_changeset_boundary_for_each_operation():
    operations = [
        {"method": "POST", "url": "/api/data/v9.2/accounts", "body": {"name": "A"}},
        {"method": "PATCH", "url": "/api/data/v9.2/accounts(1)", "body": {"name": "B"}},
        {"method": "DELETE", "url": "/api/data/v9.2/accounts(2)", "body": None},
    ]

    _, body = build_batch(operations)

    payload = body.decode("utf-8")
    boundary_match = re.search(r"boundary=(changeset_[^\r\n;]+)", payload)
    assert boundary_match, payload
    changeset_boundary = boundary_match.group(1)

    pattern = rf"--{re.escape(changeset_boundary)}\r\nContent-Type: application/http"
    occurrences = re.findall(pattern, payload)
    assert len(occurrences) == len(operations)

    closing_marker = f"--{changeset_boundary}--"
    assert closing_marker in payload


def test_build_batch_mixed_get_and_write_operations():
    operations = [
        {"method": "GET", "url": "/api/data/v9.2/accounts?$top=1", "body": None},
        {"method": "POST", "url": "/api/data/v9.2/accounts", "body": {"name": "C"}},
        {"method": "PATCH", "url": "/api/data/v9.2/accounts(123)", "body": {"name": "Updated"}},
        {"method": "GET", "url": "/api/data/v9.2/accounts?$skip=1", "body": None},
    ]

    batch_id, body = build_batch(operations)

    payload = body.decode("utf-8")

    # Identify the dynamically generated changeset boundary.
    boundary_match = re.search(r"boundary=(changeset_[^\r\n;]+)", payload)
    assert boundary_match, payload
    changeset_boundary = boundary_match.group(1)

    # There should be a single changeset containing exactly the write operations.
    write_pattern = rf"--{re.escape(changeset_boundary)}\r\nContent-Type: application/http"
    write_occurrences = re.findall(write_pattern, payload)
    assert len(write_occurrences) == 2

    # GET requests should be outside the changeset and reference the batch boundary directly.
    get_pattern = (
        rf"--{re.escape(batch_id)}\r\nContent-Type: application/http\r\n"
        r"Content-Transfer-Encoding: binary\r\nContent-ID: (\d+)"
    )
    get_occurrences = re.findall(get_pattern, payload)
    assert get_occurrences == ["1", "4"], payload

    # Ensure the changeset is closed and the full batch terminator is present.
    assert f"--{changeset_boundary}--" in payload
    assert payload.rstrip().endswith(f"--{batch_id}--")
