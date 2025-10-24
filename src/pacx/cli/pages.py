from __future__ import annotations

"""Typer commands that orchestrate Power Pages exports and imports."""

from collections.abc import Sequence
from typing import Annotated

import typer
from rich import print

from ..cli_utils import resolve_dataverse_host_from_context
from ..clients.dataverse import DataverseClient
from ..clients.power_pages import PowerPagesClient
from ._pages_utils import ensure_mapping, load_json_or_path, merge_manifest_keys
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Power Pages site ops")


@app.command("download")
@handle_cli_errors
def pages_download(
    ctx: typer.Context,
    website_id: Annotated[
        str,
        typer.Option(..., help="adx_website id GUID (without braces)"),
    ],
    tables: Annotated[
        str,
        typer.Option(
            "core",
            help="Table selection preset (core|full|comma-separated list, defaults to 'core')",
        ),
    ],
    binaries: Annotated[
        bool,
        typer.Option(
            False,
            help="Enable default binary provider (annotations); disabled unless specified",
        ),
    ],
    out: Annotated[str, typer.Option("site_out", help="Output directory (default: site_out)")],
    host: Annotated[
        str | None,
        typer.Option(None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"),
    ],
    include_files: Annotated[
        bool,
        typer.Option(True, help="Include adx_webfiles (default: True)"),
    ],
    binary_provider: Annotated[
        list[str] | None,
        typer.Option(
            None,
            "--binary-provider",
            help=(
                "Comma-separated binary provider IDs to run (overrides --binaries and"
                " requires files to be included)"
            ),
            parser=lambda value: [item.strip() for item in (value or "").split(",") if item.strip()]
            or None,
        ),
    ],
    provider_options: Annotated[
        str | None,
        typer.Option(
            None,
            help="JSON string/path configuring custom binary providers (default: none)",
        ),
    ],
) -> None:
    """Download a Power Pages site to a local folder.

    Args:
        ctx: Typer context providing authentication state.
        website_id: Dataverse website identifier.
        tables: Table preset or explicit list to export.
        binaries: Whether to export binary providers by default.
        out: Output directory for site artifacts.
        host: Optional Dataverse host override.
        include_files: Toggle inclusion of file entity exports.
        binary_provider: Explicit provider identifiers to execute.
        provider_options: JSON string or file path configuring providers.
    """

    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    provider_opts: dict[str, dict[str, object]] = {}
    if provider_options:
        try:
            raw_options = load_json_or_path(provider_options)
            mapping = ensure_mapping(raw_options, option_name="--provider-options")
            provider_opts = {
                key: dict(ensure_mapping(value, option_name=f"--provider-options[{key}]"))
                for key, value in mapping.items()
            }
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid JSON for --provider-options: {exc}") from exc
    dv = DataverseClient(token_getter, host=resolved_host)
    pp = PowerPagesClient(dv)
    provider_names: list[str] | None = None
    if binary_provider:
        provider_names = []
        for entry in binary_provider:
            if isinstance(entry, str):
                provider_names.append(entry)
            else:
                provider_names.extend(str(item) for item in entry)
    try:
        result = pp.download_site(
            website_id,
            out,
            tables=tables,
            include_files=include_files,
            binaries=binaries,
            binary_providers=provider_names,
            provider_options=provider_opts,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    print(f"Downloaded site to {result.output_path}")
    if result.providers:
        for name, provider in result.providers.items():
            print(f"Provider {name}: {len(provider.files)} files, skipped={provider.skipped}")


@app.command("upload")
@handle_cli_errors
def pages_upload(
    ctx: typer.Context,
    website_id: Annotated[
        str,
        typer.Option(..., help="adx_website id GUID (without braces)"),
    ],
    tables: Annotated[
        str,
        typer.Option(
            "core",
            help="Table selection preset (core|full|comma-separated list, defaults to 'core')",
        ),
    ],
    src: Annotated[str, typer.Option(..., help="Source directory created by pages download")],
    host: Annotated[
        str | None,
        typer.Option(None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"),
    ],
    strategy: Annotated[
        str,
        typer.Option("replace", help="replace|merge|skip-existing|create-only (default: replace)"),
    ],
    key_config: Annotated[
        str | None,
        typer.Option(
            None,
            help="JSON string/path overriding natural keys (merged with manifest data)",
        ),
    ],
) -> None:
    """Upload a previously downloaded Power Pages site.

    Args:
        ctx: Typer context providing authentication state.
        website_id: Dataverse website identifier.
        tables: Table preset or explicit list to upload.
        src: Source directory created by :func:`pages_download`.
        host: Optional Dataverse host override.
        strategy: Conflict handling strategy.
        key_config: JSON string/path overriding natural keys.
    """

    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    pp = PowerPagesClient(dv)
    cli_keys: dict[str, Sequence[str]] = {}
    if key_config:
        try:
            raw_keys = load_json_or_path(key_config)
            mapping = ensure_mapping(raw_keys, option_name="--key-config")
            cli_keys = {
                key: [str(col) for col in value]
                for key, value in mapping.items()
                if isinstance(value, Sequence) and not isinstance(value, str | bytes)
            }
            invalid = [
                key
                for key, value in mapping.items()
                if not isinstance(value, Sequence) or isinstance(value, str | bytes)
            ]
            if invalid:
                raise ValueError(
                    "; ".join(f"{name} must map to an array of column names" for name in invalid)
                )
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid JSON for --key-config: {exc}") from exc
    key_map = merge_manifest_keys(pp, src, cli_keys or None)
    pp.upload_site(
        website_id,
        src,
        tables=tables,
        strategy=strategy,
        key_config=key_map,
    )
    print("Uploaded site content")


@app.command("diff-permissions")
@handle_cli_errors
def pages_diff_permissions(
    ctx: typer.Context,
    website_id: Annotated[str, typer.Option(..., help="adx_website id GUID")],
    src: Annotated[str, typer.Option(..., help="Local export directory")],
    host: Annotated[
        str | None,
        typer.Option(None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"),
    ],
    key_config: Annotated[
        str | None,
        typer.Option(
            None,
            help="JSON string/path overriding keys (merged with manifest defaults)",
        ),
    ],
) -> None:
    """Compare web role permissions between Dataverse and a local export.

    Args:
        ctx: Typer context providing authentication state.
        website_id: Dataverse website identifier.
        src: Local export directory.
        host: Optional Dataverse host override.
        key_config: JSON string/path overriding keys.
    """

    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    cli_keys: dict[str, Sequence[str]] = {}
    if key_config:
        try:
            raw_keys = load_json_or_path(key_config)
            mapping = ensure_mapping(raw_keys, option_name="--key-config")
            cli_keys = {
                key: [str(col) for col in value]
                for key, value in mapping.items()
                if isinstance(value, Sequence) and not isinstance(value, str | bytes)
            }
            invalid = [
                key
                for key, value in mapping.items()
                if not isinstance(value, Sequence) or isinstance(value, str | bytes)
            ]
            if invalid:
                raise ValueError(
                    "; ".join(f"{name} must map to an array of column names" for name in invalid)
                )
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid JSON for --key-config: {exc}") from exc
    pp = PowerPagesClient(dv)
    merged_keys = merge_manifest_keys(pp, src, cli_keys or None)
    plan = pp.diff_permissions(website_id, src, key_config=merged_keys)
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
]
