"""Binary export providers for Power Pages assets."""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

import httpx

from ..clients.dataverse import DataverseClient


@dataclass(slots=True)
class ProviderFile:
    """Metadata for a file emitted by a binary provider."""

    path: Path
    checksum: str
    size: int
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderResult:
    """Result summary returned by a provider."""

    name: str
    files: list[ProviderFile] = field(default_factory=list)
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "files": [
                {
                    "path": str(f.path),
                    "checksum": f.checksum,
                    "size": f.size,
                    "extra": f.extra,
                }
                for f in self.files
            ],
            "skipped": self.skipped,
            "errors": list(self.errors),
        }


class ProviderContext(Protocol):
    dv: DataverseClient
    website_id: str
    output_dir: Path
    webfiles: Sequence[Mapping[str, object]]


class BinaryExportProvider(Protocol):
    """Protocol implemented by Power Pages binary export providers."""

    name: str

    def export(
        self, ctx: ProviderContext, options: Mapping[str, object] | None = None
    ) -> ProviderResult: ...


class AnnotationBinaryProvider:
    """Download web file annotations (notes) as binary payloads."""

    name = "annotations"

    def export(
        self, ctx: ProviderContext, options: Mapping[str, object] | None = None
    ) -> ProviderResult:
        out_dir = ctx.output_dir / "files_bin"
        out_dir.mkdir(parents=True, exist_ok=True)
        top = self._parse_top(options)
        result = ProviderResult(name=self.name)

        for wf in ctx.webfiles:
            wf_id = str(wf.get("adx_webfileid") or wf.get("id") or "").strip()
            if not wf_id:
                result.skipped += 1
                continue
            for note in self._iter_notes(ctx, wf_id=wf_id, top=top):
                fname = note.get("filename") or f"{note.get('annotationid')}.bin"
                fname_raw = str(fname)
                sanitized = Path(fname_raw.replace("\\", "/")).name
                if sanitized in {"", ".", ".."}:
                    sanitized = f"{note.get('annotationid')}.bin"
                document = note.get("documentbody")
                if not document:
                    result.skipped += 1
                    continue
                raw = base64.b64decode(str(document))
                target = out_dir / sanitized
                target.write_bytes(raw)
                checksum = hashlib.sha256(raw).hexdigest()
                (out_dir / f"{sanitized}.sha256").write_text(checksum, encoding="utf-8")
                result.files.append(
                    ProviderFile(
                        path=target.relative_to(ctx.output_dir),
                        checksum=checksum,
                        size=len(raw),
                        extra={"annotationid": str(note.get("annotationid"))},
                    )
                )
        return result

    @staticmethod
    def _parse_top(options: Mapping[str, object] | None) -> int | None:
        """Return a validated ``$top`` value if provided by the user."""

        if not options:
            return None
        raw = options.get("top")
        if raw is None:
            return None
        try:
            parsed = int(cast(int | str, raw))
        except (TypeError, ValueError):
            return None
        return parsed

    def _iter_notes(
        self, ctx: ProviderContext, *, wf_id: str, top: int | None
    ) -> Iterator[Mapping[str, object]]:
        """Yield annotation records for a given web file across all pages."""

        next_url: str | None = None
        while True:
            if next_url:
                page_resp = ctx.dv.http.get(next_url)
                page = cast(dict[str, object], page_resp.json())
            else:
                page = ctx.dv.list_records(
                    "annotations",
                    select="annotationid,filename,documentbody,_objectid_value",
                    filter=f"_objectid_value eq {wf_id}",
                    top=top,
                )
            for note in page.get("value", []):
                if isinstance(note, Mapping):
                    yield note
            raw_next = self._extract_next_link(page)
            if not raw_next:
                break
            next_url = raw_next

    @staticmethod
    def _extract_next_link(payload: Mapping[str, object]) -> str | None:
        for key in ("@odata.nextLink", "odata.nextLink"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None


class AzureBlobVirtualFileProvider:
    """Fetch virtual file payloads stored in Azure Blob Storage."""

    name = "azure-blob"

    def __init__(
        self,
        *,
        credential: object | None = None,
        http_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.credential = credential
        self._http_factory = http_factory

    def _build_client(self) -> httpx.Client:
        if self._http_factory:
            return self._http_factory()
        timeout = float(os.getenv("PACX_BLOB_TIMEOUT", "30"))
        return httpx.Client(timeout=timeout)

    def export(
        self, ctx: ProviderContext, options: Mapping[str, object] | None = None
    ) -> ProviderResult:
        result = ProviderResult(name=self.name)
        root = ctx.output_dir / "files_virtual"
        root.mkdir(parents=True, exist_ok=True)
        opt = dict(options or {})
        path_field_raw = opt.get("path_field", "adx_virtualfilestorepath")
        path_field = str(path_field_raw)
        token_env_raw = opt.get("sas_env")
        token_env = str(token_env_raw) if token_env_raw else None
        sas_token = os.getenv(token_env) if token_env else None

        with self._build_client() as client:
            for wf in ctx.webfiles:
                blob_url = wf.get(path_field)
                if not blob_url:
                    result.skipped += 1
                    continue
                url = str(blob_url)
                if sas_token:
                    token = sas_token.lstrip("?")
                    if token:
                        separator = "&" if "?" in url else "?"
                        url = f"{url}{separator}{token}"
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except Exception as exc:  # pragma: no cover - logged for manifest consumers
                    result.errors.append(f"{url}: {exc}")
                    continue
                name_source = (
                    wf.get("adx_name")
                    or wf.get("adx_partialurl")
                    or wf.get("adx_webfileid")
                    or "file.bin"
                )
                fname = str(name_source)
                fname = fname.replace("/", "_")
                target = root / fname
                target.write_bytes(resp.content)
                checksum = hashlib.sha256(resp.content).hexdigest()
                result.files.append(
                    ProviderFile(
                        path=target.relative_to(ctx.output_dir),
                        checksum=checksum,
                        size=len(resp.content),
                        extra={"source": url},
                    )
                )
        return result


def normalize_provider_name(name: str) -> str:
    """Return the canonical provider identifier for a given alias."""

    key = name.lower()
    if key == "annotations":
        return "annotations"
    if key in {"azure", "azure-blob", "blob"}:
        return "azure-blob"
    raise ValueError(f"Unknown binary provider: {name}")


def resolve_providers(
    names: Iterable[str],
    *,
    options: Mapping[str, Mapping[str, object]] | None = None,
) -> list[BinaryExportProvider]:
    """Instantiate providers by name."""

    resolved: list[BinaryExportProvider] = []
    for name in names:
        canonical = normalize_provider_name(name)
        if canonical == "annotations":
            resolved.append(AnnotationBinaryProvider())
        elif canonical == "azure-blob":
            resolved.append(AzureBlobVirtualFileProvider())
        else:  # pragma: no cover - normalize_provider_name validates names
            raise ValueError(f"Unknown binary provider: {name}")
    # attach options metadata for later use (stored externally)
    return resolved


def provider_options_for_manifest(
    names: Sequence[str],
    options: Mapping[str, Mapping[str, object]] | None,
) -> dict[str, Mapping[str, object]]:
    """Serialize provider options for manifest output."""

    out: dict[str, Mapping[str, object]] = {}
    opts = options or {}
    for n in names:
        if n in opts:
            out[n] = opts[n]
    return out
