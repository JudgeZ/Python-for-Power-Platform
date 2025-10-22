"""Power Pages permissions diff utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from ..clients.dataverse import DataverseClient
from ..clients.power_pages import DEFAULT_NATURAL_KEYS


PERMISSION_FOLDERS = {
    "entitypermissions": "adx_entitypermissions",
    "wp_access": "adx_webpageaccesscontrolrules",
    "webroles": "adx_webroles",
}


@dataclass
class DiffEntry:
    entityset: str
    action: str  # create|update|delete
    key: Tuple[str, ...]
    local: Mapping[str, object] | None
    remote: Mapping[str, object] | None


def _load_local_records(base: Path, folder: str) -> List[Mapping[str, object]]:
    out: List[Mapping[str, object]] = []
    target = base / folder
    if not target.exists():
        return out
    for jf in target.glob("*.json"):
        out.append(json.loads(jf.read_text(encoding="utf-8")))
    return out


def _key_for(record: Mapping[str, object], keys: Sequence[str]) -> Tuple[str, ...]:
    return tuple(str(record.get(k, "")).lower() for k in keys)


def diff_permissions(
    dv: DataverseClient,
    website_id: str,
    base_dir: str,
    *,
    key_config: Mapping[str, Sequence[str]] | None = None,
) -> List[DiffEntry]:
    base = Path(base_dir)
    keys = {k: tuple(v) for k, v in DEFAULT_NATURAL_KEYS.items()}
    if key_config:
        for entity, cols in key_config.items():
            keys[entity.lower()] = tuple(cols)

    results: List[DiffEntry] = []
    for folder, entity in PERMISSION_FOLDERS.items():
        local_records = _load_local_records(base, folder)
        key_cols = keys.get(entity.lower(), ("adx_name",))
        remote = dv.list_records(
            entity,
            select="*",
            filter=f"_adx_websiteid_value eq {website_id}" if "_adx_websiteid_value" in key_cols else None,
            top=5000,
        ).get("value", [])

        local_map: Dict[Tuple[str, ...], Mapping[str, object]] = {
            _key_for(rec, key_cols): rec for rec in local_records
        }
        remote_map: Dict[Tuple[str, ...], Mapping[str, object]] = {
            _key_for(rec, key_cols): rec for rec in remote
        }

        for key in sorted(set(local_map) | set(remote_map)):
            local_rec = local_map.get(key)
            remote_rec = remote_map.get(key)
            if local_rec and not remote_rec:
                results.append(DiffEntry(entityset=entity, action="create", key=key, local=local_rec, remote=None))
            elif remote_rec and not local_rec:
                results.append(DiffEntry(entityset=entity, action="delete", key=key, local=None, remote=remote_rec))
            else:
                # compare normalized JSON
                if json.dumps(local_rec, sort_keys=True) != json.dumps(remote_rec, sort_keys=True):
                    results.append(DiffEntry(entityset=entity, action="update", key=key, local=local_rec, remote=remote_rec))
    return results
