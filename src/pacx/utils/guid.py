"""Utilities for working with Dataverse GUID values."""

from __future__ import annotations

__all__ = ["sanitize_guid"]


def sanitize_guid(value: str) -> str:
    """Return a GUID stripped of surrounding braces and whitespace.

    Dataverse APIs accept GUIDs with or without surrounding braces. In order to
    avoid subtle issues when composing URLs (for example ``entityset({guid})``)
    this helper removes any leading/trailing whitespace and a single pair of
    braces. Inner braces are preserved so alternate key segments remain
    untouched.

    Args:
        value: GUID string that may include braces or surrounding whitespace.

    Returns:
        A sanitized GUID string ready for use in a Dataverse request path.
    """

    trimmed = value.strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        trimmed = trimmed[1:-1]
    return trimmed.strip()
