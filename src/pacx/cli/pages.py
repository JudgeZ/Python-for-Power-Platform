"""Typer commands that orchestrate Power Pages exports, imports, and runtime ops."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import typer
from rich import print

from ..cli_utils import (
    resolve_dataverse_host_from_context,
    resolve_environment_id_from_context,
)
from ..clients.dataverse import DataverseClient
from ..clients.power_pages import PowerPagesClient
from ..clients.power_pages_admin import (
    DEFAULT_API_VERSION as ADMIN_DEFAULT_API_VERSION,
)
from ..clients.power_pages_admin import (
    PowerPagesAdminClient,
    WebsiteOperationHandle,
)
from ._pages_utils import ensure_mapping, load_json_or_path, merge_manifest_keys
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Power Pages site ops")
websites_app = typer.Typer(help="Power Pages website lifecycle and security")
app.add_typer(websites_app, name="websites")


WEBSITE_ID_OPTION = typer.Option(..., help="adx_website id GUID (without braces)")
TABLES_OPTION = typer.Option(
    "core",
    help="Table selection preset (core|full|comma-separated list, defaults to 'core')",
)
BINARIES_OPTION = typer.Option(
    False,
    help="Enable default binary provider (annotations); disabled unless specified",
)
OUT_DIR_OPTION = typer.Option("site_out", help="Output directory (default: site_out)")
PAGES_HOST_OPTION = typer.Option(
    None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"
)
INCLUDE_FILES_OPTION = typer.Option(True, help="Include adx_webfiles (default: True)")


def _parse_binary_provider(value: str | None) -> list[str] | None:
    items = [item.strip() for item in (value or "").split(",") if item.strip()]
    return items or None


BINARY_PROVIDER_OPTION = typer.Option(
    None,
    "--binary-provider",
    help=(
        "Comma-separated binary provider IDs to run (overrides --binaries and requires files "
        "to be included)"
    ),
    parser=_parse_binary_provider,
)
PROVIDER_OPTIONS_OPTION = typer.Option(
    None, help="JSON string/path configuring custom binary providers (default: none)"
)


def _admin_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["pages_admin_api_version"] = override
        return override
    cached = data.get("pages_admin_api_version")
    if isinstance(cached, str) and cached:
        return cached
    data["pages_admin_api_version"] = ADMIN_DEFAULT_API_VERSION
    return ADMIN_DEFAULT_API_VERSION


def _build_admin_client(ctx: typer.Context, api_version: str) -> PowerPagesAdminClient:
    token_getter = get_token_getter(ctx)
    return PowerPagesAdminClient(token_getter, api_version=api_version)


def _echo_json(data: Mapping[str, Any]) -> None:
    if data:
        print(json.dumps(dict(data), indent=2, sort_keys=True))


def _handle_admin_operation(
    action: str,
    handle: WebsiteOperationHandle,
    client: PowerPagesAdminClient,
    *,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    if handle.operation_location:
        print(
            f"[cyan]{action} submitted[/cyan] operation={handle.operation_id} "
            f"location={handle.operation_location}"
        )
        if not wait:
            if handle.metadata:
                _echo_json(handle.metadata)
            print("Use --wait to poll for completion.")
            return
        final = client.wait_for_operation(
            handle.operation_location, interval=interval, timeout=timeout
        )
        status = final.get("status") or final.get("state")
        normalized_status = str(status or "").strip().lower()
        success_states = {"succeeded", "success", "completed", "complete"}
        failure_states = {"failed", "failure", "canceled", "cancelled"}
        if normalized_status and normalized_status not in success_states:
            prefix = "failed" if normalized_status in failure_states else "completed with errors"
            message = (
                f"[red]{action} {prefix}[/red] status={status}"
                if status
                else f"[red]{action} {prefix}[/red]"
            )
            print(message)
            if final:
                _echo_json(final)
            raise typer.Exit(1)
        if status:
            print(f"[green]{action} completed[/green] status={status}")
        else:
            print(f"[green]{action} completed[/green]")
        if final:
            _echo_json(final)
    else:
        print(f"[green]{action} completed[/green]")
        if handle.metadata:
            _echo_json(handle.metadata)


@websites_app.callback()
@handle_cli_errors
def websites_root(
    ctx: typer.Context,
    api_version: str = typer.Option(
        ADMIN_DEFAULT_API_VERSION,
        help="Power Pages admin API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    _admin_api_version(ctx, api_version)


@websites_app.command("start")
@handle_cli_errors
def websites_start(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="Website ID (GUID)"),
    environment_id: str | None = typer.Option(
        None,
        help="Environment ID (defaults to profile configuration)",
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Pages admin API version override",
    ),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Wait for the operation to complete", show_default=True
    ),
    interval: float = typer.Option(2.0, help="Seconds between polling attempts"),
    timeout: float = typer.Option(900.0, help="Maximum seconds to wait for completion"),
) -> None:
    version = _admin_api_version(ctx, api_version)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_admin_client(ctx, version)
    handle = client.start_website(environment, website_id)
    _handle_admin_operation(
        "Website start", handle, client, wait=wait, interval=interval, timeout=timeout
    )


@websites_app.command("stop")
@handle_cli_errors
def websites_stop(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="Website ID (GUID)"),
    environment_id: str | None = typer.Option(
        None,
        help="Environment ID (defaults to profile configuration)",
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Pages admin API version override",
    ),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Wait for the operation to complete", show_default=True
    ),
    interval: float = typer.Option(2.0, help="Seconds between polling attempts"),
    timeout: float = typer.Option(900.0, help="Maximum seconds to wait for completion"),
) -> None:
    version = _admin_api_version(ctx, api_version)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_admin_client(ctx, version)
    handle = client.stop_website(environment, website_id)
    _handle_admin_operation(
        "Website stop", handle, client, wait=wait, interval=interval, timeout=timeout
    )


@websites_app.command("scan")
@handle_cli_errors
def websites_scan(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="Website ID (GUID)"),
    environment_id: str | None = typer.Option(
        None,
        help="Environment ID (defaults to profile configuration)",
    ),
    mode: str = typer.Option(
        "quick",
        "--mode",
        case_sensitive=False,
        help="Scan mode: quick or deep (default: quick)",
        show_default=True,
    ),
    lcid: int | None = typer.Option(
        None,
        help="Optional LCID for quick scans (ignored for deep scans)",
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Pages admin API version override",
    ),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Wait for the operation to complete", show_default=True
    ),
    interval: float = typer.Option(5.0, help="Seconds between polling attempts"),
    timeout: float = typer.Option(900.0, help="Maximum seconds to wait for completion"),
) -> None:
    version = _admin_api_version(ctx, api_version)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_admin_client(ctx, version)
    mode_value = mode.lower().strip()
    if mode_value == "quick":
        handle = client.start_quick_scan(environment, website_id, lcid=lcid)
        label = "Quick scan"
    elif mode_value == "deep":
        if lcid is not None:
            raise typer.BadParameter("--lcid is only valid for quick scans")
        handle = client.start_deep_scan(environment, website_id)
        label = "Deep scan"
    else:  # pragma: no cover - validated by Typer choices
        raise typer.BadParameter("--mode must be quick or deep")
    _handle_admin_operation(label, handle, client, wait=wait, interval=interval, timeout=timeout)


@websites_app.command("waf")
@handle_cli_errors
def websites_waf(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="Website ID (GUID)"),
    environment_id: str | None = typer.Option(
        None,
        help="Environment ID (defaults to profile configuration)",
    ),
    action: str = typer.Option(
        "status",
        "--action",
        case_sensitive=False,
        help="WAF action: enable, disable, status, get-rules, or set-rules",
        show_default=True,
    ),
    rules: str | None = typer.Option(
        None,
        help="JSON string/path describing rules for set-rules",
    ),
    rule_type: str | None = typer.Option(
        None,
        help="Optional rule type filter for get-rules",
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Pages admin API version override",
    ),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Wait for asynchronous operations", show_default=True
    ),
    interval: float = typer.Option(2.0, help="Seconds between polling attempts"),
    timeout: float = typer.Option(900.0, help="Maximum seconds to wait for completion"),
) -> None:
    version = _admin_api_version(ctx, api_version)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_admin_client(ctx, version)
    action_value = action.lower().strip()
    if action_value == "enable":
        handle = client.enable_waf(environment, website_id)
        _handle_admin_operation(
            "WAF enable", handle, client, wait=wait, interval=interval, timeout=timeout
        )
    elif action_value == "disable":
        handle = client.disable_waf(environment, website_id)
        _handle_admin_operation(
            "WAF disable", handle, client, wait=wait, interval=interval, timeout=timeout
        )
    elif action_value == "status":
        data = client.get_waf_status(environment, website_id)
        if data:
            _echo_json(data)
        else:
            print("No WAF status returned")
    elif action_value == "get-rules":
        data = client.get_waf_rules(environment, website_id, rule_type=rule_type)
        if data:
            _echo_json(data)
        else:
            print("No WAF rules returned")
    elif action_value == "set-rules":
        if not rules:
            raise typer.BadParameter("--rules is required when --action set-rules")
        raw_rules = load_json_or_path(rules)
        if not isinstance(raw_rules, Mapping):
            raise typer.BadParameter("--rules must be a JSON object")
        handle = client.create_waf_rules(environment, website_id, dict(raw_rules))
        _handle_admin_operation(
            "WAF rules update", handle, client, wait=wait, interval=interval, timeout=timeout
        )
    else:  # pragma: no cover - validated by Typer choices
        raise typer.BadParameter("Unsupported --action value")


@websites_app.command("visibility")
@handle_cli_errors
def websites_visibility(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="Website ID (GUID)"),
    environment_id: str | None = typer.Option(
        None,
        help="Environment ID (defaults to profile configuration)",
    ),
    payload: str = typer.Option(
        ..., "--payload", help="JSON string/path describing visibility settings"
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Pages admin API version override",
    ),
) -> None:
    version = _admin_api_version(ctx, api_version)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_admin_client(ctx, version)
    raw_payload = load_json_or_path(payload)
    if not isinstance(raw_payload, Mapping):
        raise typer.BadParameter("--payload must be a JSON object")
    result = client.update_site_visibility(environment, website_id, dict(raw_payload))
    if result:
        _echo_json(result)
    else:
        print("[green]Site visibility updated[/green]")


@app.command("download")
@handle_cli_errors
def pages_download(
    ctx: typer.Context,
    website_id: str = WEBSITE_ID_OPTION,
    tables: str = TABLES_OPTION,
    binaries: bool = BINARIES_OPTION,
    out: str = OUT_DIR_OPTION,
    host: str | None = PAGES_HOST_OPTION,
    include_files: bool = INCLUDE_FILES_OPTION,
    binary_provider: list[str] | None = BINARY_PROVIDER_OPTION,
    provider_options: str | None = PROVIDER_OPTIONS_OPTION,
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
            errors = getattr(provider, "errors", None)
            if errors:
                for error in errors:
                    print(f"Provider {name} error: {error}")


@app.command("upload")
@handle_cli_errors
def pages_upload(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option(
        "core",
        help="Table selection preset (core|full|comma-separated list, defaults to 'core')",
    ),
    src: str = typer.Option(..., help="Source directory created by pages download"),
    host: str | None = typer.Option(
        None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"
    ),
    strategy: str = typer.Option(
        "replace", help="replace|merge|skip-existing|create-only (default: replace)"
    ),
    key_config: str | None = typer.Option(
        None,
        help=("JSON string/path overriding natural keys (map entity -> array of column names)"),
    ),
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
    website_id: str = typer.Option(..., help="adx_website id GUID"),
    src: str = typer.Option(..., help="Local export directory"),
    host: str | None = typer.Option(
        None, help="Dataverse host to use (defaults to profile or DATAVERSE_HOST)"
    ),
    key_config: str | None = typer.Option(
        None,
        help=("JSON string/path overriding keys (map entity -> array of column names)"),
    ),
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
