"""Power Pages Dataverse client helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from typing import Any, cast

from ..errors import HttpError
from ..odata import build_alternate_key_segment
from ..power_pages.constants import DEFAULT_NATURAL_KEYS
from ..power_pages.diff import DiffEntry, diff_permissions
from ..power_pages.providers import (
    ProviderResult,
    normalize_provider_name,
    provider_options_for_manifest,
    resolve_providers,
)
from .dataverse import DataverseClient

CORE_TABLES: list[tuple[str, str, str, str]] = [
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

EXTRA_TABLES: list[tuple[str, str, str, str]] = [
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


@dataclass
class DownloadResult:
    """Details about a site download."""

    output_path: Path
    summary: dict[str, int]
    manifest_path: Path
    providers: dict[str, ProviderResult] = field(default_factory=dict)


logger = logging.getLogger(__name__)


class PowerPagesClient:
    """Sync selected adx_* tables to/from filesystem as JSON files per record."""

    def __init__(self, dv: DataverseClient) -> None:
        """Create a Power Pages helper bound to an existing Dataverse client.

        Args:
            dv: Configured :class:`DataverseClient` used for all data access.
        """
        self.dv = dv

    @staticmethod
    def _select_sets(tables: str | Iterable[str] = "core") -> list[tuple[str, str, str, str]]:
        if isinstance(tables, str):
            tokens = [token.strip().lower() for token in tables.split(",") if token.strip()]
        else:
            tokens = [str(token).strip().lower() for token in tables if str(token).strip()]

        include_core = False
        include_full = False
        wanted: set[str] = set()
        for label in tokens:
            if label == "full":
                include_full = True
            elif label == "core":
                include_core = True
            else:
                wanted.add(label)

        selected: list[tuple[str, str, str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()

        def add_choice(choice: tuple[str, str, str, str]) -> None:
            if choice not in seen:
                selected.append(choice)
                seen.add(choice)

        all_tables = CORE_TABLES + EXTRA_TABLES

        if include_full:
            for entry in all_tables:
                add_choice(entry)
        elif include_core:
            for entry in CORE_TABLES:
                add_choice(entry)

        if wanted:
            for entry in all_tables:
                folder, entityset, _, _ = entry
                if folder.lower() in wanted or entityset.lower() in wanted:
                    add_choice(entry)

        return selected

    def normalize_provider_inputs(
        self,
        *,
        binaries: bool,
        binary_providers: Iterable[str] | None,
        include_files: bool,
        provider_options: Mapping[str, Mapping[str, object]] | None = None,
    ) -> tuple[list[str], dict[str, Mapping[str, object]]]:
        """Normalize provider inputs coming from the CLI layer.

        Args:
            binaries: ``True`` when the ``--binaries`` flag is set.
            binary_providers: Explicit provider names from ``--binary-provider``.
            include_files: Indicates whether file downloads are allowed.
            provider_options: Raw options mapping provided on the CLI.

        Returns:
            Tuple containing the resolved provider names and per-provider option
            mappings suitable for :func:`resolve_providers`.
        """

        providers: list[str] = []
        if binary_providers:
            providers = [str(name) for name in binary_providers]
        elif binaries:
            providers = ["annotations"]

        if providers and not include_files:
            raise ValueError("Binary providers require include_files=True")

        normalized_options: dict[str, Mapping[str, object]] = {}
        if provider_options:
            for key, value in provider_options.items():
                if not isinstance(value, Mapping):
                    raise ValueError(f"Provider options for {key!s} must be a mapping")
                normalized_options[str(key)] = dict(value)

        return providers, normalized_options

    def key_config_from_manifest(
        self,
        src_dir: str,
        overrides: Mapping[str, Sequence[str]] | None = None,
    ) -> dict[str, list[str]]:
        """Compose natural key configuration using defaults and overrides.

        Args:
            src_dir: Source directory containing ``manifest.json``.
            overrides: Caller-supplied natural key configuration.

        Returns:
            Mapping from entity logical name to natural key column list.
        """

        base = Path(src_dir)
        merged: dict[str, list[str]] = {
            key.lower(): list(values) for key, values in DEFAULT_NATURAL_KEYS.items()
        }
        manifest_path = base / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive logging only
                logger.debug("Failed to load manifest keys from %s: %s", manifest_path, exc)
            else:
                natural_keys = data.get("natural_keys", {})
                if isinstance(natural_keys, Mapping):
                    for entity, columns in natural_keys.items():
                        if isinstance(columns, Sequence) and not isinstance(columns, str | bytes):
                            merged[str(entity).lower()] = [str(col) for col in columns]

        if overrides:
            for entity, columns in overrides.items():
                if isinstance(columns, Sequence) and not isinstance(columns, str | bytes):
                    merged[str(entity).lower()] = [str(col) for col in columns]

        return merged

    @staticmethod
    def _extract_next_link(payload: Mapping[str, object]) -> str | None:
        for key in ("@odata.nextLink", "odata.nextLink"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _list_all_records(
        self,
        entityset: str,
        *,
        select: str,
        filter_expr: str | None,
        top: int = 5000,
    ) -> list[Mapping[str, object]]:
        payload = self.dv.list_records(entityset, select=select, filter=filter_expr, top=top)
        records = [
            cast(Mapping[str, object], obj)
            for obj in cast(Iterable[object], payload.get("value", []))
            if isinstance(obj, Mapping)
        ]
        next_link = self._extract_next_link(payload)
        while next_link:
            page = cast(dict[str, Any], self.dv.http.get(next_link).json())
            records.extend(
                cast(Mapping[str, object], obj)
                for obj in cast(Iterable[object], page.get("value", []))
                if isinstance(obj, Mapping)
            )
            next_link = self._extract_next_link(page)
        return records

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
        """Download site tables and binary assets into a directory structure.

        Args:
            website_id: Dataverse website identifier.
            out_dir: Destination directory for the export.
            tables: Table selection preset (``core``/``full``) or CSV list.
            include_files: Whether to download file records and binaries.
            binaries: When ``True``, export default binary providers.
            binary_providers: Explicit binary providers to execute.
            provider_options: Optional per-provider configuration mapping.

        Returns:
            :class:`DownloadResult` describing generated content and providers.
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        sets = self._select_sets(tables)
        if not include_files:
            sets = [s for s in sets if s[0] != "files"]

        summary: dict[str, int] = {}
        webfiles: list[Mapping[str, object]] = []
        for folder, entityset, key, select in sets:
            (out / folder).mkdir(parents=True, exist_ok=True)
            filter_expr = None
            if entityset == "adx_websites":
                filter_expr = f"adx_websiteid eq {website_id}"
            elif "_adx_websiteid_value" in select:
                filter_expr = f"_adx_websiteid_value eq {website_id}"
            data = self._list_all_records(
                entityset,
                select=select,
                filter_expr=filter_expr,
                top=5000,
            )
            summary[folder] = len(data)
            if entityset == "adx_webfiles":
                webfiles.extend(data)
            for obj in data:
                rec_id = obj.get(key) or obj.get("id") or obj.get("name")
                name = str(rec_id).replace("/", "_")
                (out / folder / f"{name}.json").write_text(
                    json.dumps(obj, indent=2), encoding="utf-8"
                )

        provider_names, normalized_options = self.normalize_provider_inputs(
            binaries=binaries,
            binary_providers=binary_providers,
            include_files=include_files,
            provider_options=provider_options,
        )

        providers: dict[str, ProviderResult] = {}
        resolved_options: dict[str, Mapping[str, object]] = {}
        for opt_key, opt_value in normalized_options.items():
            try:
                canonical_key = normalize_provider_name(opt_key)
            except ValueError:
                canonical_key = opt_key
            resolved_options[canonical_key] = opt_value

        resolved_names: list[str] = list(provider_names)
        if provider_names and include_files:
            resolved = resolve_providers(provider_names, options=resolved_options)
            resolved_names = [prov.name for prov in resolved]
            ctx = _ProviderContext(self.dv, website_id, out, webfiles)
            for prov in resolved:
                opts = resolved_options.get(prov.name)
                providers[prov.name] = prov.export(ctx, options=opts)

        manifest: dict[str, object] = {
            "website_id": website_id,
            "tables": summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "providers": {name: res.to_dict() for name, res in providers.items()},
            "provider_options": provider_options_for_manifest(resolved_names, resolved_options),
            "natural_keys": DEFAULT_NATURAL_KEYS,
        }
        manifest_path = out / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return DownloadResult(
            output_path=out, summary=summary, manifest_path=manifest_path, providers=providers
        )

    def upload_site(
        self,
        website_id: str,
        src_dir: str,
        *,
        tables: str | Iterable[str] = "full",
        strategy: str = "replace",
        key_config: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        """Push local JSON records back into Dataverse tables.

        Args:
            website_id: Dataverse website identifier.
            src_dir: Directory containing exported JSON files.
            tables: Table selection preset (``core``/``full``) or CSV list.
            strategy: Conflict handling strategy (``replace``, ``merge``, etc.).
            key_config: Natural key overrides keyed by entity logical name.
        """
        base = Path(src_dir)
        sets = self._select_sets(tables)
        if key_config is None:
            key_map: dict[str, list[str]] = self.key_config_from_manifest(src_dir)
        else:
            key_map = self.key_config_from_manifest(src_dir, key_config)

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
                    key_values = {col: obj[col] for col in natural}
                    key_segment = build_alternate_key_segment(key_values)
                    path = f"{entityset}({key_segment})"
                    if strategy == "create-only":
                        try:
                            self.dv.http.get(path)
                        except HttpError as exc:
                            if exc.status_code == 404:
                                self.dv.create_record(entityset, obj)
                            else:
                                raise
                        else:
                            continue
                    elif strategy == "skip-existing":
                        try:
                            self.dv.http.get(path)
                        except HttpError as exc:
                            if exc.status_code == 404:
                                self.dv.create_record(entityset, obj)
                            else:
                                raise
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

    def _handle_record_with_id(
        self, entityset: str, record_id: str, body: Mapping[str, object], strategy: str
    ) -> None:
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
            self.dv.update_record(entityset, record_id, dict(merged))
            return
        self.dv.update_record(entityset, record_id, dict(body))

    def diff_permissions(
        self,
        website_id: str,
        base_dir: str,
        *,
        key_config: Mapping[str, Sequence[str]] | None = None,
    ) -> list[DiffEntry]:
        """Compare Dataverse and local permission state for a website.

        Args:
            website_id: Dataverse website identifier.
            base_dir: Directory containing exported JSON records.
            key_config: Natural key overrides keyed by entity logical name.

        Returns:
            Provider diff structure produced by :func:`diff_permissions`.
        """
        if key_config is None:
            merged_keys = self.key_config_from_manifest(base_dir)
        else:
            merged_keys = {str(k).lower(): list(v) for k, v in key_config.items()}
        return diff_permissions(self.dv, website_id, base_dir, key_config=merged_keys)


@dataclass(slots=True)
class _ProviderContext:
    dv: DataverseClient
    website_id: str
    output_dir: Path
    webfiles: Sequence[Mapping[str, object]]
