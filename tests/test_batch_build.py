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
