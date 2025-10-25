from __future__ import annotations

from urllib.parse import quote


def _escape_odata_string(value: str) -> str:
    """Escape single quotes by doubling them per the OData specification."""

    return value.replace("'", "''")


def _encode_odata_value(value: str) -> str:
    """Percent-encode a string for safe use inside an OData path segment."""

    escaped = _escape_odata_string(value)
    # Encode all characters except the unreserved RFC 3986 set to keep OData compatible.
    return quote(escaped, safe="-_.~")


def build_alternate_key_segment(key_map: dict[str, str]) -> str:
    """Return e.g. "accountnumber='A-1',name='Contoso'" with escaping and encoding."""

    items = []
    for k, v in key_map.items():
        if v is None:
            raise ValueError(f"Alternate key '{k}' has None value")
        encoded_value = _encode_odata_value(str(v))
        items.append(f"{k}='{encoded_value}'")
    return ",".join(items)
