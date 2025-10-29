from __future__ import annotations

from pathlib import Path


def test_ci_examples_doc_exists() -> None:
    path = Path("docs/user-manual/04-ci-examples.md")
    assert path.exists(), "CI examples doc is missing"


def test_ci_examples_doc_contains_key_sections() -> None:
    text = Path("docs/user-manual/04-ci-examples.md").read_text(encoding="utf-8")
    assert "Device Code" in text
    assert "Client Credentials" in text
