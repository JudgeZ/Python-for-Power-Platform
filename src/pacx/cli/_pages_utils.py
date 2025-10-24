"""Utility helpers for Power Pages CLI commands."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence

from ..clients.power_pages import PowerPagesClient

logger = logging.getLogger(__name__)


def load_json_or_path(value: str) -> object:
    """Load JSON from a string or a filesystem path."""
    path = Path(value)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = value
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - handled by caller
        raise ValueError(str(exc)) from exc


def ensure_mapping(data: object, *, option_name: str) -> MutableMapping[str, object]:
    """Validate that ``data`` is a mapping for the given CLI option."""
    if not isinstance(data, Mapping):
        raise ValueError(f"{option_name} must be a JSON object")
    return {str(key): value for key, value in data.items()}


def merge_manifest_keys(
    client: PowerPagesClient,
    src_dir: str,
    overrides: Mapping[str, Sequence[str]] | None,
) -> MutableMapping[str, list[str]]:
    """Merge defaults, manifest keys, and overrides using the client."""
    merged = client.key_config_from_manifest(src_dir, overrides=overrides)
    return {key: list(value) for key, value in merged.items()}
