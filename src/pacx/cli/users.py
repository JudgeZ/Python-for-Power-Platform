from __future__ import annotations

import importlib
from typing import Any, cast

import typer
from rich import print

from ..clients.user_management import (
    DEFAULT_API_VERSION,
    UserManagementOperationHandle,
)
from ..clients.user_management import (
    UserManagementClient as _DefaultUserManagementClient,
)
from ..models.user_management import AsyncOperationStatus
from .common import get_token_getter, handle_cli_errors


def _resolve_client_class() -> type[_DefaultUserManagementClient]:
    try:
        module = importlib.import_module("pacx.cli")
    except Exception:  # pragma: no cover - defensive fallback
        return _DefaultUserManagementClient

    client_cls = getattr(module, "UserManagementClient", None)
    if client_cls is None:
        return _DefaultUserManagementClient
    return cast(type[_DefaultUserManagementClient], client_cls) or _DefaultUserManagementClient


def _build_client(
    ctx: typer.Context,
    *,
    api_version: str | None = None,
) -> _DefaultUserManagementClient:
    token_getter = get_token_getter(ctx)
    client_cls = _resolve_client_class()
    if api_version is None:
        return client_cls(token_getter)
    return client_cls(token_getter, api_version=api_version)


def _ensure_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["api_version"] = override
        return override
    return cast(str, data.get("api_version", DEFAULT_API_VERSION))


def _print_operation_result(action: str, handle: UserManagementOperationHandle) -> None:
    location = handle.operation_location
    if location:
        print(
            f"[green]{action} accepted[/green] operation={handle.operation_id} "
            f"location={location}"
        )
    else:
        print(f"[green]{action} accepted[/green]")
    if handle.metadata:
        print(handle.metadata)


def _format_status(status: AsyncOperationStatus) -> dict[str, Any]:
    return status.model_dump(by_alias=True, exclude_none=True)


def _resolve_operation_url(handle: UserManagementOperationHandle) -> str | None:
    if handle.operation_location:
        return handle.operation_location
    operation_id = handle.metadata.get("id") if handle.metadata else None
    if operation_id:
        return f"usermanagement/operations/{operation_id}"
    return None


def _wait_for_completion(
    client: _DefaultUserManagementClient,
    handle: UserManagementOperationHandle,
    *,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    if not wait:
        return
    operation_url = _resolve_operation_url(handle)
    if not operation_url:
        print("[yellow]No operation URL returned; skipping wait.[/yellow]")
        return
    status = client.wait_for_operation(operation_url, interval=interval, timeout=timeout)
    print(f"[green]Operation completed[/green] status={status.status}")
    payload = _format_status(status)
    if payload:
        print(payload)


app = typer.Typer(help="Manage Power Platform user assignments.")
admin_role_app = typer.Typer(help="Manage admin role assignments for users.")
app.add_typer(admin_role_app, name="admin-role")


@app.callback()
@handle_cli_errors
def users_root(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Power Platform API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    """Configure defaults for user management commands."""

    ctx.ensure_object(dict)["api_version"] = api_version


@admin_role_app.command("apply")
@handle_cli_errors
def apply_admin_role_command(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Azure AD object ID of the target user."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Wait for the async operation to finish."
    ),
    interval: float = typer.Option(2.0, help="Polling interval in seconds."),
    timeout: float = typer.Option(600.0, help="Maximum seconds to wait for completion."),
) -> None:
    """Apply the default admin role to a user."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    handle = client.apply_admin_role(user_id)
    _print_operation_result("Admin role apply", handle)
    _wait_for_completion(client, handle, wait=wait, interval=interval, timeout=timeout)


@admin_role_app.command("remove")
@handle_cli_errors
def remove_admin_role_command(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Azure AD object ID of the target user."),
    role_definition_id: str = typer.Option(
        ...,
        "--role-definition-id",
        "-r",
        help="Role definition ID to revoke from the user.",
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Wait for the async operation to finish."
    ),
    interval: float = typer.Option(2.0, help="Polling interval in seconds."),
    timeout: float = typer.Option(600.0, help="Maximum seconds to wait for completion."),
) -> None:
    """Remove a previously applied admin role."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    handle = client.remove_admin_role(user_id, role_definition_id)
    _print_operation_result("Admin role removal", handle)
    _wait_for_completion(client, handle, wait=wait, interval=interval, timeout=timeout)


@admin_role_app.command("list")
@handle_cli_errors
def list_admin_roles_command(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Azure AD object ID of the target user."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """List admin roles assigned to a user."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    assignments = client.list_admin_roles(user_id)
    if not assignments.value:
        print("[yellow]No admin roles assigned.[/yellow]")
        return
    for assignment in assignments.value:
        summary = assignment.model_dump(by_alias=True, exclude_none=True)
        name = summary.get("roleDisplayName") or summary.get("roleDefinitionId")
        scope = summary.get("scope", "tenant")
        print(
            f"[bold]{name}[/bold] roleDefinitionId={summary.get('roleDefinitionId')} scope={scope}"
        )


UserManagementClient = _DefaultUserManagementClient

__all__ = ["app", "UserManagementClient"]
