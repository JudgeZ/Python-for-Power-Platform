
from __future__ import annotations

def _escape_odata_string(value: str) -> str:
    # Escape single quotes by doubling them per OData
    return value.replace("'", "''")


def build_alternate_key_segment(key_map: dict[str, str]) -> str:
    """Return e.g. "accountnumber='A-1',name='Contoso'" with proper escaping."""
    items = []
    for k, v in key_map.items():
        if v is None:
            raise ValueError(f"Alternate key '{k}' has None value")
        items.append(f"{k}='{_escape_odata_string(str(v))}'")
    return ",".join(items)
