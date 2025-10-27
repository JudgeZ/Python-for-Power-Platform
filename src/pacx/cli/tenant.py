"""Tenant settings CLI surface."""

from __future__ import annotations

import json
from typing import Any, cast

import typer

from ..clients.tenant_settings import (
    DEFAULT_API_VERSION,
    TenantOperationResult,
    TenantSettingsClient,
)
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Tenant administration commands.")
settings_app = typer.Typer(help="Manage tenant settings.")
feature_app = typer.Typer(help="Manage tenant feature controls.")

app.add_typer(settings_app, name="settings")
app.add_typer(feature_app, name="feature")


def _set_api_version(ctx: typer.Context, api_version: str) -> None:
    ctx.ensure_object(dict)["tenant_api_version"] = api_version


def _resolve_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["tenant_api_version"] = override
        return override
    return cast(str, data.get("tenant_api_version", DEFAULT_API_VERSION))


def _build_client(ctx: typer.Context, api_version: str) -> TenantSettingsClient:
    token_getter = get_token_getter(ctx)
    return TenantSettingsClient(token_getter, api_version=api_version)


def _parse_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - typer validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def _print_operation(result: TenantOperationResult, success_message: str) -> None:
    if result.resource is not None:
        print(result.resource.model_dump(by_alias=True, exclude_none=True))
        return
    if result.accepted:
        location = result.operation_location
        suffix = f" location={location}" if location else ""
        print(f"[green]{success_message} accepted for async processing.[/green]{suffix}")
        return
    print(f"[green]{success_message}.[/green]")


@app.callback()
def tenant_root(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Tenant settings API version (defaults to 2024-03-01-preview)",
    ),
) -> None:
    """Initialize tenant CLI context."""

    _set_api_version(ctx, api_version)


@settings_app.command("get")
@handle_cli_errors
def settings_get(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Tenant settings API version override."),
) -> None:
    """Retrieve tenant settings."""

    version = _resolve_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    settings = client.get_settings()
    print(settings.model_dump(by_alias=True, exclude_none=True))


@settings_app.command("update")
@handle_cli_errors
def settings_update(
    ctx: typer.Context,
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing the setting updates."
    ),
    prefer_async: bool = typer.Option(
        False,
        "--async/--no-async",
        help="Request asynchronous processing (sets Prefer: respond-async).",
    ),
    api_version: str | None = typer.Option(None, help="Tenant settings API version override."),
) -> None:
    """Patch tenant settings with a JSON payload."""

    version = _resolve_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    body = _parse_payload(payload)
    result = client.update_settings(body, prefer_async=prefer_async)
    _print_operation(result, "Tenant settings update")


@settings_app.command("request-access")
@handle_cli_errors
def settings_request_access(
    ctx: typer.Context,
    justification: str = typer.Option(..., help="Reason for requesting elevated access."),
    requested_settings: list[str] = typer.Option(
        [],
        "--setting",
        help="Optional setting identifiers requiring access (repeat for multiple).",
    ),
    api_version: str | None = typer.Option(None, help="Tenant settings API version override."),
) -> None:
    """Request admin access to change tenant settings."""

    version = _resolve_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    payload: dict[str, Any] = {"justification": justification}
    if requested_settings:
        payload["requestedSettings"] = requested_settings
    client.request_settings_access(payload)
    print("[green]Tenant settings access request submitted.[/green]")


@feature_app.command("list")
@handle_cli_errors
def feature_list(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Tenant settings API version override."),
) -> None:
    """List feature controls configured for the tenant."""

    version = _resolve_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    controls = client.list_feature_controls()
    for control in controls.value:
        status = "enabled" if control.value else "disabled"
        print(f"[bold]{control.name or 'unknown'}[/bold] status={status}")
    if controls.next_link:
        print(f"Next page: {controls.next_link}")


@feature_app.command("update")
@handle_cli_errors
def feature_update(
    ctx: typer.Context,
    feature_name: str = typer.Argument(..., help="Feature identifier to update."),
    payload: str = typer.Option(..., "--payload", help="JSON payload for the feature update."),
    prefer_async: bool = typer.Option(
        False,
        "--async/--no-async",
        help="Request asynchronous processing (sets Prefer: respond-async).",
    ),
    api_version: str | None = typer.Option(None, help="Tenant settings API version override."),
) -> None:
    """Update a feature control toggle."""

    version = _resolve_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    body = _parse_payload(payload)
    result = client.update_feature_control(feature_name, body, prefer_async=prefer_async)
    _print_operation(result, f"Feature '{feature_name}' update")


@feature_app.command("request-access")
@handle_cli_errors
def feature_request_access(
    ctx: typer.Context,
    feature_name: str = typer.Argument(..., help="Feature identifier to request access for."),
    justification: str = typer.Option(..., help="Reason for requesting feature access."),
    api_version: str | None = typer.Option(None, help="Tenant settings API version override."),
) -> None:
    """Request permission to modify a feature control."""

    version = _resolve_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    payload = {"justification": justification}
    client.request_feature_access(feature_name, payload)
    print(
        f"[green]Feature access request submitted for '{feature_name}'.[/green]"
    )


__all__ = [
    "app",
    "feature_app",
    "feature_list",
    "feature_request_access",
    "feature_update",
    "settings_app",
    "settings_get",
    "settings_request_access",
    "settings_update",
]
