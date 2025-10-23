from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich import print

from ..clients.dataverse import DataverseClient
from ..clients.power_pages import PowerPagesClient
from ..cli_utils import resolve_dataverse_host_from_context
from ..power_pages.diff import diff_permissions
from .common import get_token_getter, handle_cli_errors

logger = logging.getLogger(__name__)

app = typer.Typer(help="Power Pages site ops")

BINARY_PROVIDER_OPTION = typer.Option(
    None,
    "--binary-provider",
    help="Comma-separated binary provider IDs to run",
    parser=lambda value: [
        item.strip() for item in (value or "").split(",") if item.strip()
    ]
    or None,
)


@app.command("download")
@handle_cli_errors
def pages_download(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option(
        "core", help="Table selection: core|full|comma-separated logical names"
    ),
    binaries: bool = typer.Option(
        False, help="Use default binary provider (annotations)"
    ),
    out: str = typer.Option("site_out", help="Output directory (default: site_out)"),
    host: str | None = typer.Option(
        None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"
    ),
    include_files: bool = typer.Option(True, help="Include adx_webfiles (default: True)"),
    binary_provider: list[str] | None = BINARY_PROVIDER_OPTION,
    provider_options: str | None = typer.Option(
        None, help="JSON string/path configuring custom binary providers"
    ),
):
    """Download a Power Pages site to a local folder."""

    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    if binary_provider and not include_files:
        raise typer.BadParameter("Binary providers require --include-files True")
    provider_opts: dict[str, dict[str, object]] = {}
    if provider_options:
        try:
            path = Path(provider_options)
            if path.exists():
                provider_opts = json.loads(path.read_text(encoding="utf-8"))
            else:
                provider_opts = json.loads(provider_options)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON for --provider-options: {exc}") from exc
    dv = DataverseClient(token_getter, host=resolved_host)
    pp = PowerPagesClient(dv)
    providers: list[str] | None
    providers = list(binary_provider) if binary_provider else None
    result = pp.download_site(
        website_id,
        out,
        tables=tables,
        include_files=include_files,
        binaries=binaries,
        binary_providers=providers,
        provider_options=provider_opts,
    )
    print(f"Downloaded site to {result.output_path}")
    if result.providers:
        for name, provider in result.providers.items():
            print(f"Provider {name}: {len(provider.files)} files, skipped={provider.skipped}")


@app.command("upload")
@handle_cli_errors
def pages_upload(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option(
        "core", help="Table selection: core|full|comma-separated logical names"
    ),
    src: str = typer.Option(..., help="Source directory created by pages download"),
    host: str | None = typer.Option(
        None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"
    ),
    strategy: str = typer.Option(
        "replace", help="replace|merge|skip-existing|create-only (default: replace)"
    ),
    key_config: str | None = typer.Option(
        None, help="JSON string/path overriding natural keys"
    ),
):
    """Upload a previously downloaded Power Pages site."""

    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    pp = PowerPagesClient(dv)
    manifest_path = Path(src) / "manifest.json"
    manifest_keys: dict[str, list[str]] = {}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_keys = {k: list(v) for k, v in data.get("natural_keys", {}).items()}
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.debug("Failed to load manifest keys from %s: %s", manifest_path, exc)
    cli_keys: dict[str, list[str]] = {}
    if key_config:
        try:
            path = Path(key_config)
            if path.exists():
                cli_keys = json.loads(path.read_text(encoding="utf-8"))
            else:
                cli_keys = json.loads(key_config)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON for --key-config: {exc}") from exc
    key_map = manifest_keys
    key_map.update(cli_keys)
    pp.upload_site(website_id, src, tables=tables, strategy=strategy, key_config=key_map)
    print("Uploaded site content")


@app.command("diff-permissions")
@handle_cli_errors
def pages_diff_permissions(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID"),
    src: str = typer.Option(..., help="Local export directory"),
    host: str | None = typer.Option(
        None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"
    ),
    key_config: str | None = typer.Option(
        None, help="JSON string/path overriding keys"
    ),
):
    """Compare web role permissions between Dataverse and a local export."""

    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    manifest_path = Path(src) / "manifest.json"
    manifest_keys: dict[str, list[str]] = {}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_keys = {k: list(v) for k, v in data.get("natural_keys", {}).items()}
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.debug("Failed to load manifest keys from %s: %s", manifest_path, exc)
    cli_keys: dict[str, list[str]] = {}
    if key_config:
        try:
            path = Path(key_config)
            if path.exists():
                cli_keys = json.loads(path.read_text(encoding="utf-8"))
            else:
                cli_keys = json.loads(key_config)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON for --key-config: {exc}") from exc
    merged_keys = manifest_keys
    merged_keys.update(cli_keys)
    plan = diff_permissions(dv, website_id, src, key_config=merged_keys)
    if not plan:
        print("No permission differences detected.")
        return
    print("Permission diff plan:")
    for entry in plan:
        key_repr = ",".join(entry.key)
        print(f"- {entry.entityset}: {entry.action} [{key_repr}]")


__all__ = [
    "app",
    "pages_download",
    "pages_upload",
    "pages_diff_permissions",
    "BINARY_PROVIDER_OPTION",
]
