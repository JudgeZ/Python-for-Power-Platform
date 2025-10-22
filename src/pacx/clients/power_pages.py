
from __future__ import annotations

import json
import base64
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterable

from ..clients.dataverse import DataverseClient


CORE_TABLES = [
    ("websites", "adx_websites", "adx_websiteid", "adx_websiteid,adx_name"),
    ("pages", "adx_webpages", "adx_webpageid", "adx_webpageid,adx_name,adx_partialurl,_adx_websiteid_value"),
    ("files", "adx_webfiles", "adx_webfileid", "adx_webfileid,adx_name,adx_partialurl,_adx_websiteid_value"),
    ("snippets", "adx_contentsnippets", "adx_contentsnippetid", "adx_contentsnippetid,adx_name,adx_value,_adx_websiteid_value"),
    ("templates", "adx_pagetemplates", "adx_pagetemplateid", "adx_pagetemplateid,adx_name,adx_type,_adx_websiteid_value"),
    ("sitemarkers", "adx_sitemarkers", "adx_sitemarkerid", "adx_sitemarkerid,adx_name,_adx_webpageid_value,_adx_websiteid_value"),
]

# Additional coverage
EXTRA_TABLES = [
    ("weblinksets", "adx_weblinksets", "adx_weblinksetid", "adx_weblinksetid,adx_name,_adx_websiteid_value"),
    ("weblinks", "adx_weblinks", "adx_weblinkid", "adx_weblinkid,adx_name,_adx_weblinksetid_value,_adx_websiteid_value"),
    ("wp_access", "adx_webpageaccesscontrolrules", "adx_webpageaccesscontrolruleid", "adx_webpageaccesscontrolruleid,adx_name,adx_right,_adx_websiteid_value"),
    ("webroles", "adx_webroles", "adx_webroleid", "adx_webroleid,adx_name,_adx_websiteid_value"),
    ("entitypermissions", "adx_entitypermissions", "adx_entitypermissionid", "adx_entitypermissionid,adx_name,adx_entitylogicalname,adx_accessrightsmask,_adx_websiteid_value"),
    ("redirects", "adx_redirects", "adx_redirectid", "adx_redirectid,adx_name,adx_sourceurl,adx_targeturl,_adx_websiteid_value"),
]


class PowerPagesClient:
    """Sync selected adx_* tables to/from filesystem as JSON files per record.

    - *download_site*: creates subfolders named after each table group and writes one JSON file per record.
    - *upload_site*: reads all JSON files back and upserts by key.

    You can choose *tables*: "core" (default), "full" (core + extra), or a custom list of entity logical names.
    """

    def __init__(self, dv: DataverseClient) -> None:
        self.dv = dv

    @staticmethod
    def _select_sets(tables: str | Iterable[str] = "core"):
        if isinstance(tables, str):
            tv = tables.lower()
            if tv == "core":
                return CORE_TABLES
            if tv == "full":
                return CORE_TABLES + EXTRA_TABLES
            # comma-separated list of entity logical names
            wanted = set(s.strip().lower() for s in tv.split(",") if s.strip())
        else:
            wanted = set(s.strip().lower() for s in tables)
        out = []
        for tup in CORE_TABLES + EXTRA_TABLES:
            folder, entityset, key, select = tup
            if entityset.lower() in wanted or not isinstance(tables, str):
                out.append(tup)
        return out

    def download_site(
        self,
        website_id: str,
        out_dir: str,
        *,
        tables: str | Iterable[str] = "core",
        top: int = 5000,
        include_files: bool = True,
        binaries: bool = False,
    ) -> str:
        """Download site content into ``out_dir``.

        When ``include_files`` is ``False`` the ``files`` folder is skipped. Set ``binaries`` to
        ``True`` to fetch related annotation binaries after exporting metadata.
        """

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        sets = (
            CORE_TABLES
            if tables == "core"
            else (CORE_TABLES + EXTRA_TABLES if tables == "full" else self._select_sets(tables))
        )
        summary: Dict[str, int] = {}
        webfiles: list[dict] = []
        for folder, entityset, key, select in sets:
            if folder == "files" and not include_files:
                continue
            (out / folder).mkdir(parents=True, exist_ok=True)
            filter_expr = None
            # Most ADX tables expose _adx_websiteid_value; safe to filter when that field is in select
            if "_adx_websiteid_value" in select:
                filter_expr = f"_adx_websiteid_value eq {website_id}"
            data = self.dv.list_records(entityset, select=select, filter=filter_expr, top=top).get("value", [])
            summary[folder] = len(data)
            if folder == "files":
                webfiles = data
            for obj in data:
                rec_id = obj.get(key) or obj.get("id") or obj.get("name")  # fallback
                name = str(rec_id).replace("/", "_")
                (out / folder / f"{name}.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")

        (out / "site.json").write_text(json.dumps({"website_id": website_id, "summary": summary}, indent=2), encoding="utf-8")

        if binaries and include_files and webfiles:
            self.download_webfile_binaries(webfiles, str(out))

        return str(out)

    def download_webfile_binaries(self, webfiles: list[dict], out_dir: str) -> None:
        """Fetch annotation binaries for each ``adx_webfile`` and write to ``files_bin``."""

        out = Path(out_dir) / "files_bin"
        out.mkdir(parents=True, exist_ok=True)
        for wf in webfiles:
            wf_id = wf.get("adx_webfileid") or wf.get("id")
            if not wf_id:
                continue
            data = self.dv.list_records(
                "annotations",
                select="annotationid,filename,documentbody,_objectid_value",
                filter=f"_objectid_value eq {wf_id}",
                top=50,
            )
            for note in data.get("value", []):
                fname = note.get("filename") or f"{note.get('annotationid')}.bin"
                b64 = note.get("documentbody")
                if not b64:
                    continue
                raw = base64.b64decode(b64)
                p = out / fname
                p.write_bytes(raw)
                (out / f"{fname}.sha256").write_text(hashlib.sha256(raw).hexdigest(), encoding="utf-8")

    def upload_site(self, website_id: str, src_dir: str, *, strategy: str = "replace") -> None:
        """Upload JSON artifacts from ``src_dir`` using the provided ``strategy``."""

        if strategy not in {"replace", "merge", "skip-existing", "create-only"}:
            raise ValueError(f"Unknown strategy: {strategy}")

        if strategy == "replace":
            self._upload_site_replace(src_dir)
        else:
            self._upload_site_with_strategy(src_dir, strategy)

    def _upload_site_replace(self, src_dir: str) -> None:
        base = Path(src_dir)
        for folder, entityset, key, _ in CORE_TABLES + EXTRA_TABLES:
            p = base / folder
            if not p.exists():
                continue
            for jf in p.glob("*.json"):
                obj = json.loads(jf.read_text(encoding="utf-8"))
                rid = obj.get(key)
                if rid:
                    try:
                        self.dv.update_record(entityset, rid, obj)
                    except Exception:
                        self.dv.create_record(entityset, obj)
                else:
                    self.dv.create_record(entityset, obj)

    def _upload_site_with_strategy(self, src_dir: str, strategy: str) -> None:
        base = Path(src_dir)
        for folder, entityset, key, _ in CORE_TABLES + EXTRA_TABLES:
            p = base / folder
            if not p.exists():
                continue
            for jf in p.glob("*.json"):
                obj = json.loads(jf.read_text(encoding="utf-8"))
                rid = obj.get(key)
                if rid:
                    if strategy in {"skip-existing", "create-only"}:
                        continue
                    if strategy == "merge":
                        try:
                            current = self.dv.get_record(entityset, rid)
                        except Exception:
                            current = {}
                        merged = {**current, **obj}
                        self.dv.update_record(entityset, rid, merged)
                    else:  # strategy == "replace" handled earlier
                        self.dv.update_record(entityset, rid, obj)
                else:
                    if strategy == "skip-existing":
                        continue
                    self.dv.create_record(entityset, obj)
