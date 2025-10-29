from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich import print
from rich.json import JSON

from ..clients.environment_management import (
    DEFAULT_API_VERSION,
    EnvironmentManagementClient,
    EnvironmentOperationHandle,
)
from ..models.environment_management import (
    EnvironmentBackupRequest,
    EnvironmentCopyRequest,
    EnvironmentCreateRequest,
    EnvironmentLifecycleOperation,
    EnvironmentResetRequest,
    EnvironmentRestoreRequest,
)
from ..models.power_platform import EnvironmentSummary
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Manage Power Platform environments.")
ops_app = typer.Typer(help="Inspect environment operations.")
groups_app = typer.Typer(help="Manage environment groups.")
app.add_typer(ops_app, name="ops")
app.add_typer(groups_app, name="groups")


def _load_json(value: str) -> dict[str, Any]:
    candidate = value.strip()
    if not candidate:
        raise typer.BadParameter("JSON payload cannot be empty.")
    if candidate.startswith("@"):
        path = Path(candidate[1:]).expanduser()
        if not path.exists():
            raise typer.BadParameter(f"File not found: {path}")
        candidate = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - option validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return payload


def _print_handle(action: str, handle: EnvironmentOperationHandle) -> None:
    status = handle.operation.status if handle.operation else None
    operation_id = handle.operation.operation_id if handle.operation else None
    print(f"[green]{action} request accepted[/green]")
    if handle.operation_location:
        print(f"operation-location={handle.operation_location}")
    if operation_id:
        print(f"operation-id={operation_id}")
    if status:
        print(f"status={status}")
    if handle.retry_after is not None:
        print(f"retry-after={handle.retry_after}s")


def _print_summary(summary: EnvironmentSummary) -> None:
    name = summary.name or summary.properties.get("displayName") or summary.id or "<unknown>"
    print(f"[bold]{name}[/bold] id={summary.id} type={summary.type}")


def _print_json(data: Any) -> None:
    try:
        print(JSON.from_data(data))
    except Exception:  # pragma: no cover - fallback when Rich JSON fails
        print(data)


def _client(ctx: typer.Context, api_version: str | None = None) -> EnvironmentManagementClient:
    token_getter = get_token_getter(ctx)
    version = api_version or ctx.obj.get("api_version", DEFAULT_API_VERSION)
    return EnvironmentManagementClient(token_getter, api_version=version)


@app.callback()
def defaults(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Environment management API version (default: 2022-03-01-preview)",
    ),
) -> None:
    ctx.ensure_object(dict)["api_version"] = api_version


@app.command("list")
@handle_cli_errors
def list_environments(
    ctx: typer.Context,
    top: int | None = typer.Option(None, help="Limit number of environments returned."),
    continuation_token: str | None = typer.Option(
        None, help="Continuation token from a previous listing."
    ),
) -> None:
    """List environments available to the authenticated principal."""

    client = _client(ctx)
    page = client.list_environments(top=top, continuation_token=continuation_token)
    for environment in page.value:
        _print_summary(environment)
    if page.continuation_token:
        print(f"[yellow]continuation-token[/yellow] {page.continuation_token}")


@app.command("show")
@handle_cli_errors
def show_environment(ctx: typer.Context, environment_id: str) -> None:
    """Show metadata for a specific environment."""

    client = _client(ctx)
    summary = client.get_environment(environment_id)
    _print_json(summary.model_dump(by_alias=True, exclude_none=True))


@app.command("create")
@handle_cli_errors
def create_environment(
    ctx: typer.Context,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
    validate_only: bool = typer.Option(
        False,
        "--validate-only/--no-validate-only",
        help="Validate without performing the create operation.",
    ),
) -> None:
    """Provision a new Power Platform environment."""

    client = _client(ctx)
    request = EnvironmentCreateRequest.model_validate(_load_json(payload))
    handle = client.create_environment(request, validate_only=validate_only)
    _print_handle("environment create", handle)


@app.command("delete")
@handle_cli_errors
def delete_environment(
    ctx: typer.Context,
    environment_id: str,
    validate_only: bool = typer.Option(
        False,
        "--validate-only/--no-validate-only",
        help="Validate without deleting the environment.",
    ),
) -> None:
    """Delete an environment."""

    client = _client(ctx)
    handle = client.delete_environment(environment_id, validate_only=validate_only)
    _print_handle("environment delete", handle)


@app.command("copy")
@handle_cli_errors
def copy_environment(
    ctx: typer.Context,
    environment_id: str,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
    wait: bool = typer.Option(False, "--wait", help="Wait for completion"),
    timeout: int = typer.Option(900, "--timeout", help="Timeout seconds when waiting"),
) -> None:
    """Copy an environment into a new target environment."""

    client = _client(ctx)
    request = EnvironmentCopyRequest.model_validate(_load_json(payload))
    handle = client.copy_environment(environment_id, request)
    _print_handle("environment copy", handle)
    if wait and handle.operation_location:
        from ..utils.operation_monitor import OperationMonitor

        monitor = OperationMonitor()
        result = monitor.track(client.http, handle.operation_location, timeout_s=timeout)
        _print_json(result)


@app.command("reset")
@handle_cli_errors
def reset_environment(
    ctx: typer.Context,
    environment_id: str,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
    wait: bool = typer.Option(False, "--wait", help="Wait for completion"),
    timeout: int = typer.Option(900, "--timeout", help="Timeout seconds when waiting"),
) -> None:
    """Reset an environment to a prior state."""

    client = _client(ctx)
    request = EnvironmentResetRequest.model_validate(_load_json(payload))
    handle = client.reset_environment(environment_id, request)
    _print_handle("environment reset", handle)
    if wait and handle.operation_location:
        from ..utils.operation_monitor import OperationMonitor

        monitor = OperationMonitor()
        result = monitor.track(client.http, handle.operation_location, timeout_s=timeout)
        _print_json(result)


@app.command("backup")
@handle_cli_errors
def backup_environment(
    ctx: typer.Context,
    environment_id: str,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
    wait: bool = typer.Option(False, "--wait", help="Wait for completion"),
    timeout: int = typer.Option(900, "--timeout", help="Timeout seconds when waiting"),
) -> None:
    """Schedule an environment backup."""

    client = _client(ctx)
    request = EnvironmentBackupRequest.model_validate(_load_json(payload))
    handle = client.backup_environment(environment_id, request)
    _print_handle("environment backup", handle)
    if wait and handle.operation_location:
        from ..utils.operation_monitor import OperationMonitor

        monitor = OperationMonitor()
        result = monitor.track(client.http, handle.operation_location, timeout_s=timeout)
        _print_json(result)


@app.command("restore")
@handle_cli_errors
def restore_environment(
    ctx: typer.Context,
    environment_id: str,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
    wait: bool = typer.Option(False, "--wait", help="Wait for completion"),
    timeout: int = typer.Option(900, "--timeout", help="Timeout seconds when waiting"),
) -> None:
    """Restore an environment from backup."""

    client = _client(ctx)
    request = EnvironmentRestoreRequest.model_validate(_load_json(payload))
    handle = client.restore_environment(environment_id, request)
    _print_handle("environment restore", handle)
    if wait and handle.operation_location:
        from ..utils.operation_monitor import OperationMonitor

        monitor = OperationMonitor()
        result = monitor.track(client.http, handle.operation_location, timeout_s=timeout)
        _print_json(result)


@app.command("enable-managed")
@handle_cli_errors
def enable_managed(ctx: typer.Context, environment_id: str) -> None:
    """Enable managed environment governance."""

    client = _client(ctx)
    handle = client.enable_managed_environment(environment_id)
    _print_handle("managed environment enable", handle)


@app.command("disable-managed")
@handle_cli_errors
def disable_managed(ctx: typer.Context, environment_id: str) -> None:
    """Disable managed environment governance."""

    client = _client(ctx)
    handle = client.disable_managed_environment(environment_id)
    _print_handle("managed environment disable", handle)


@ops_app.command("list")
@handle_cli_errors
def list_operations(ctx: typer.Context, environment_id: str) -> None:
    """List recent operations for an environment."""

    client = _client(ctx)
    operations = client.list_operations(environment_id)
    for op in operations:
        _print_operation(op)


def _print_operation(operation: EnvironmentLifecycleOperation) -> None:
    status = operation.status or "Unknown"
    print(f"{operation.operation_id or '<unknown>'}: status={status}")


@ops_app.command("show")
@handle_cli_errors
def show_operation(ctx: typer.Context, operation_id: str) -> None:
    """Show the current status of a long-running operation."""

    client = _client(ctx)
    operation = client.get_operation(operation_id)
    _print_json(operation.model_dump(by_alias=True, exclude_none=True))


@groups_app.command("list")
@handle_cli_errors
def list_groups(ctx: typer.Context) -> None:
    """List environment groups."""

    client = _client(ctx)
    groups = client.list_environment_groups()
    for group in groups:
        name = group.get("displayName") or group.get("name") or group.get("id")
        print(f"[bold]{name or '<unknown>'}[/bold] id={group.get('id')}")


@groups_app.command("show")
@handle_cli_errors
def show_group(ctx: typer.Context, environment_group_id: str) -> None:
    """Show details for an environment group."""

    client = _client(ctx)
    group = client.get_environment_group(environment_group_id)
    _print_json(group)


@groups_app.command("create")
@handle_cli_errors
def create_group(
    ctx: typer.Context,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
) -> None:
    """Create a new environment group."""

    client = _client(ctx)
    group = client.create_environment_group(_load_json(payload))
    _print_json(group)


@groups_app.command("update")
@handle_cli_errors
def update_group(
    ctx: typer.Context,
    environment_group_id: str,
    payload: str = typer.Option(..., "--payload", help="JSON payload or @file for the request."),
) -> None:
    """Update an existing environment group."""

    client = _client(ctx)
    group = client.update_environment_group(environment_group_id, _load_json(payload))
    _print_json(group)


@groups_app.command("delete")
@handle_cli_errors
def delete_group(ctx: typer.Context, environment_group_id: str) -> None:
    """Delete an environment group."""

    client = _client(ctx)
    handle = client.delete_environment_group(environment_group_id)
    _print_handle("environment group delete", handle)


@groups_app.command("add")
@handle_cli_errors
def add_environment(
    ctx: typer.Context,
    environment_group_id: str,
    environment_id: str,
) -> None:
    """Add an environment to a group."""

    client = _client(ctx)
    handle = client.add_environment_to_group(environment_group_id, environment_id)
    _print_handle("environment group add", handle)


@groups_app.command("remove")
@handle_cli_errors
def remove_environment(
    ctx: typer.Context,
    environment_group_id: str,
    environment_id: str,
) -> None:
    """Remove an environment from a group."""

    client = _client(ctx)
    handle = client.remove_environment_from_group(environment_group_id, environment_id)
    _print_handle("environment group remove", handle)


__all__ = ["app"]
