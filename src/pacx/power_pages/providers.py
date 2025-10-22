"""Binary export providers for Power Pages assets."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

import httpx

from ..clients.dataverse import DataverseClient


@dataclass(slots=True)
class ProviderFile:
    """Metadata for a file emitted by a binary provider."""

    path: Path
    checksum: str
    size: int
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderResult:
    """Result summary returned by a provider."""

    name: str
    files: List[ProviderFile] = field(default_factory=list)
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
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

    def export(self, ctx: ProviderContext, options: Mapping[str, object] | None = None) -> ProviderResult:
        ...


class AnnotationBinaryProvider:
    """Download web file annotations (notes) as binary payloads."""

    name = "annotations"

    def export(self, ctx: ProviderContext, options: Mapping[str, object] | None = None) -> ProviderResult:
        out_dir = ctx.output_dir / "files_bin"
        out_dir.mkdir(parents=True, exist_ok=True)
        top = int((options or {}).get("top", 50))
        result = ProviderResult(name=self.name)

        for wf in ctx.webfiles:
            wf_id = str(wf.get("adx_webfileid") or wf.get("id") or "").strip()
            if not wf_id:
                result.skipped += 1
                continue
            data = ctx.dv.list_records(
                "annotations",
                select="annotationid,filename,documentbody,_objectid_value",
                filter=f"_objectid_value eq {wf_id}",
                top=top,
            )
            for note in data.get("value", []):
                fname = note.get("filename") or f"{note.get('annotationid')}.bin"
                document = note.get("documentbody")
                if not document:
                    result.skipped += 1
                    continue
                raw = base64.b64decode(document)
                target = out_dir / fname
                target.write_bytes(raw)
                checksum = hashlib.sha256(raw).hexdigest()
                (out_dir / f"{fname}.sha256").write_text(checksum, encoding="utf-8")
                result.files.append(
                    ProviderFile(
                        path=target.relative_to(ctx.output_dir),
                        checksum=checksum,
                        size=len(raw),
                        extra={"annotationid": str(note.get("annotationid"))},
                    )
                )
        return result


class AzureBlobVirtualFileProvider:
    """Fetch virtual file payloads stored in Azure Blob Storage."""

    name = "azure-blob"

    def __init__(
        self,
        *,
        credential: object | None = None,
        http_factory: callable | None = None,
    ) -> None:
        self.credential = credential
        self._http_factory = http_factory

    def _build_client(self) -> httpx.Client:
        if self._http_factory:
            return self._http_factory()
        timeout = float(os.getenv("PACX_BLOB_TIMEOUT", "30"))
        return httpx.Client(timeout=timeout)

    def export(self, ctx: ProviderContext, options: Mapping[str, object] | None = None) -> ProviderResult:
        result = ProviderResult(name=self.name)
        root = ctx.output_dir / "files_virtual"
        root.mkdir(parents=True, exist_ok=True)
        opt = dict(options or {})
        path_field = opt.get("path_field", "adx_virtualfilestorepath")
        token_env = opt.get("sas_env")
        sas_token = os.getenv(str(token_env)) if token_env else None

        with self._build_client() as client:
            for wf in ctx.webfiles:
                blob_url = wf.get(path_field)
                if not blob_url:
                    result.skipped += 1
                    continue
                url = str(blob_url)
                if sas_token and "?" not in url:
                    url = f"{url}?{sas_token}"
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except Exception as exc:  # pragma: no cover - logged for manifest consumers
                    result.errors.append(f"{url}: {exc}")
                    continue
                fname = str(wf.get("adx_name") or wf.get("adx_partialurl") or wf.get("adx_webfileid") or "file.bin")
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


def resolve_providers(
    names: Iterable[str],
    *,
    options: Mapping[str, Mapping[str, object]] | None = None,
) -> List[BinaryExportProvider]:
    """Instantiate providers by name."""

    resolved: List[BinaryExportProvider] = []
    opts = options or {}
    for name in names:
        key = name.lower()
        if key == "annotations":
            resolved.append(AnnotationBinaryProvider())
        elif key in {"azure", "azure-blob", "blob"}:
            resolved.append(AzureBlobVirtualFileProvider())
        else:
            raise ValueError(f"Unknown binary provider: {name}")
    # attach options metadata for later use (stored externally)
    return resolved


def provider_options_for_manifest(
    names: Sequence[str],
    options: Mapping[str, Mapping[str, object]] | None,
) -> Dict[str, Mapping[str, object]]:
    """Serialize provider options for manifest output."""

    out: Dict[str, Mapping[str, object]] = {}
    opts = options or {}
    for n in names:
        if n in opts:
            out[n] = opts[n]
    return out

