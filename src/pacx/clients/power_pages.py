"""Power Pages Dataverse client helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

from ..odata import build_alternate_key_segment
from ..power_pages.providers import ProviderResult, provider_options_for_manifest, resolve_providers
from .dataverse import DataverseClient


CORE_TABLES: List[tuple[str, str, str, str]] = [
    ("websites", "adx_websites", "adx_websiteid", "adx_websiteid,adx_name"),
    (
        "pages",
        "adx_webpages",
        "adx_webpageid",
        "adx_webpageid,adx_name,adx_partialurl,_adx_websiteid_value,adx_isroot",
    ),
    (
        "files",
        "adx_webfiles",
        "adx_webfileid",
        "adx_webfileid,adx_name,adx_partialurl,_adx_websiteid_value,adx_virtualfilestorepath",
    ),
    (
        "snippets",
        "adx_contentsnippets",
        "adx_contentsnippetid",
        "adx_contentsnippetid,adx_name,adx_value,_adx_websiteid_value",
    ),
    (
        "templates",
        "adx_pagetemplates",
        "adx_pagetemplateid",
        "adx_pagetemplateid,adx_name,adx_type,_adx_websiteid_value",
    ),
    (
        "sitemarkers",
        "adx_sitemarkers",
        "adx_sitemarkerid",
        "adx_sitemarkerid,adx_name,_adx_webpageid_value,_adx_websiteid_value",
    ),
]

EXTRA_TABLES: List[tuple[str, str, str, str]] = [
    (
        "weblinksets",
        "adx_weblinksets",
        "adx_weblinksetid",
        "adx_weblinksetid,adx_name,_adx_websiteid_value",
    ),
    (
        "weblinks",
        "adx_weblinks",
        "adx_weblinkid",
        "adx_weblinkid,adx_name,_adx_weblinksetid_value,_adx_websiteid_value",
    ),
    (
        "wp_access",
        "adx_webpageaccesscontrolrules",
        "adx_webpageaccesscontrolruleid",
        "adx_webpageaccesscontrolruleid,adx_name,adx_right,_adx_websiteid_value,_adx_webpageid_value",
    ),
    (
        "webroles",
        "adx_webroles",
        "adx_webroleid",
        "adx_webroleid,adx_name,_adx_websiteid_value",
    ),
    (
        "entitypermissions",
        "adx_entitypermissions",
        "adx_entitypermissionid",
        "adx_entitypermissionid,adx_name,adx_entitylogicalname,adx_accessrightsmask,_adx_websiteid_value",
    ),
    (
        "redirects",
        "adx_redirects",
        "adx_redirectid",
        "adx_redirectid,adx_name,adx_sourceurl,adx_targeturl,_adx_websiteid_value",
    ),
]


DEFAULT_NATURAL_KEYS: Dict[str, List[str]] = {
    "adx_webpages": ["adx_partialurl", "_adx_websiteid_value"],
    "adx_webfiles": ["adx_partialurl", "_adx_websiteid_value"],
    "adx_contentsnippets": ["adx_name", "_adx_websiteid_value"],
    "adx_pagetemplates": ["adx_name", "_adx_websiteid_value"],
    "adx_sitemarkers": ["adx_name", "_adx_websiteid_value"],
    "adx_weblinksets": ["adx_name", "_adx_websiteid_value"],
    "adx_weblinks": ["adx_name", "_adx_weblinksetid_value"],
    "adx_webpageaccesscontrolrules": ["adx_name", "_adx_websiteid_value"],
    "adx_webroles": ["adx_name", "_adx_websiteid_value"],
    "adx_entitypermissions": ["adx_name", "_adx_websiteid_value"],
    "adx_redirects": ["adx_sourceurl", "_adx_websiteid_value"],
}


@dataclass
class DownloadResult:
    """Details about a site download."""

    output_path: Path
    summary: Dict[str, int]
    manifest_path: Path
    providers: Dict[str, ProviderResult] = field(default_factory=dict)


class PowerPagesClient:
    """Sync selected adx_* tables to/from filesystem as JSON files per record."""

    def __init__(self, dv: DataverseClient) -> None:
        self.dv = dv

    @staticmethod
    def _select_sets(tables: str | Iterable[str] = "core") -> List[tuple[str, str, str, str]]:
        if isinstance(tables, str):
            tv = tables.lower()
            if tv == "core":
                return list(CORE_TABLES)
            if tv == "full":
                return list(CORE_TABLES + EXTRA_TABLES)
            wanted = {s.strip().lower() for s in tv.split(",") if s.strip()}
        else:
            wanted = {s.strip().lower() for s in tables}
        out: List[tuple[str, str, str, str]] = []
        for tup in CORE_TABLES + EXTRA_TABLES:
            folder, entityset, _, _ = tup
            if isinstance(tables, str):
                if entityset.lower() in wanted or folder.lower() in wanted:
                    out.append(tup)
            else:
                out.append(tup)
        return out

    def download_site(
        self,
        website_id: str,
        out_dir: str,
        *,
        tables: str | Iterable[str] = "core",
        include_files: bool = True,
        binaries: bool = False,
        binary_providers: Iterable[str] | None = None,
        provider_options: Mapping[str, Mapping[str, object]] | None = None,
    ) -> DownloadResult:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        sets = self._select_sets(tables)
        if not include_files:
            sets = [s for s in sets if s[0] != "files"]

        summary: Dict[str, int] = {}
        webfiles: List[Mapping[str, object]] = []
        for folder, entityset, key, select in sets:
            (out / folder).mkdir(parents=True, exist_ok=True)
            filter_expr = None
            if "_adx_websiteid_value" in select:
                filter_expr = f"_adx_websiteid_value eq {website_id}"
            data = self.dv.list_records(entityset, select=select, filter=filter_expr, top=5000).get("value", [])
            summary[folder] = len(data)
            if entityset == "adx_webfiles":
                webfiles.extend(data)
            for obj in data:
                rec_id = obj.get(key) or obj.get("id") or obj.get("name")
                name = str(rec_id).replace("/", "_")
                (out / folder / f"{name}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")

        provider_names: Sequence[str]
        if binary_providers is not None:
            provider_names = list(binary_providers)
        elif binaries:
            provider_names = ["annotations"]
        else:
            provider_names = []

        providers: Dict[str, ProviderResult] = {}
        resolved_options = provider_options or {}
        resolved_names: List[str] = list(provider_names)
        if provider_names and include_files:
            resolved = resolve_providers(provider_names, options=resolved_options)
            resolved_names = [prov.name for prov in resolved]
            ctx = _ProviderContext(self.dv, website_id, out, webfiles)
            for prov in resolved:
                opts = resolved_options.get(prov.name)
                providers[prov.name] = prov.export(ctx, options=opts)

        manifest = {
            "website_id": website_id,
            "tables": summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "providers": {name: res.to_dict() for name, res in providers.items()},
            "provider_options": provider_options_for_manifest(resolved_names, resolved_options),
            "natural_keys": DEFAULT_NATURAL_KEYS,
        }
        manifest_path = out / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return DownloadResult(output_path=out, summary=summary, manifest_path=manifest_path, providers=providers)

    def upload_site(
        self,
        website_id: str,
        src_dir: str,
        *,
        tables: str | Iterable[str] = "full",
        strategy: str = "replace",
        key_config: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        base = Path(src_dir)
        sets = self._select_sets(tables)
        key_map: Dict[str, Sequence[str]] = dict(DEFAULT_NATURAL_KEYS)
        if key_config:
            for k, v in key_config.items():
                key_map[k.lower()] = list(v)

        for folder, entityset, key, _ in sets:
            p = base / folder
            if not p.exists():
                continue
            for jf in sorted(p.glob("*.json")):
                obj = json.loads(jf.read_text(encoding="utf-8"))
                rid = obj.get(key)
                if rid:
                    self._handle_record_with_id(entityset, rid, obj, strategy)
                    continue

                natural = key_map.get(entityset.lower())
                if natural and all(obj.get(col) for col in natural):
                    key_segment = build_alternate_key_segment({col: obj[col] for col in natural})
                    path = f"{entityset}({key_segment})"
                    if strategy == "create-only":
                        self.dv.create_record(entityset, obj)
                    elif strategy == "skip-existing":
                        try:
                            self.dv.http.patch(path, json=obj)
                        except Exception:
                            continue
                    elif strategy == "merge":
                        try:
                            current = self.dv.http.get(path).json()
                        except Exception:
                            current = {}
                        merged = {**current, **obj}
                        self.dv.http.patch(path, json=merged)
                    else:
                        self.dv.http.patch(path, json=obj)
                    continue

                if strategy == "skip-existing":
                    continue
                if strategy == "merge":
                    self.dv.create_record(entityset, obj)
                else:
                    self.dv.create_record(entityset, obj)

    def _handle_record_with_id(self, entityset: str, record_id: str, body: Mapping[str, object], strategy: str) -> None:
        if strategy == "skip-existing":
            return
        if strategy == "create-only":
            return
        if strategy == "merge":
            try:
                current = self.dv.get_record(entityset, record_id)
            except Exception:
                current = {}
            merged = {**current, **body}
            self.dv.update_record(entityset, record_id, merged)
            return
        self.dv.update_record(entityset, record_id, body)


@dataclass(slots=True)
class _ProviderContext:
    dv: DataverseClient
    website_id: str
    output_dir: Path
    webfiles: Sequence[Mapping[str, object]]

