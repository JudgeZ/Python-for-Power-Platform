from __future__ import annotations

import json
from importlib import import_module
from typing import Any, Type, cast

import typer
from rich import print

from ..cli_utils import resolve_environment_id_from_context
from ..clients.power_platform import (
    DEFAULT_API_VERSION,
    OperationHandle,
    PowerPlatformClient as _DefaultPowerPlatformClient,
)
from .common import get_token_getter, handle_cli_errors


def _resolve_client_class() -> Type[_DefaultPowerPlatformClient]:
    try:
        module = import_module("pacx.cli")
    except Exception:  # pragma: no cover - defensive fallback
        return _DefaultPowerPlatformClient

    client_cls = getattr(module, "PowerPlatformClient", None)
    if client_cls is None:
        return _DefaultPowerPlatformClient
    return cast(Type[_DefaultPowerPlatformClient], client_cls) or _DefaultPowerPlatformClient


def _build_client(
    ctx: typer.Context,
    *,
    api_version: str | None = None,
) -> _DefaultPowerPlatformClient:
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


def _parse_payload(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - option validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def _print_operation_result(action: str, handle: OperationHandle) -> None:
    if handle.operation_location:
        print(
            f"[green]{action} accepted[/green] operation={handle.operation_id} "
            f"location={handle.operation_location}"
        )
    else:
        print(f"[green]{action} accepted[/green]")
    if handle.metadata:
        print(handle.metadata)


env_app = typer.Typer(help="Manage Power Platform environments.", invoke_without_command=True)
env_group_app = typer.Typer(help="Manage Power Platform environment groups.")
apps_app = typer.Typer(help="Manage Power Apps.", invoke_without_command=True)


def _resolve_app_environment(ctx: typer.Context, option_value: str | None) -> str:
    data = ctx.ensure_object(dict)
    if option_value:
        environment = resolve_environment_id_from_context(ctx, option_value)
        data["apps_environment_id"] = environment
        return environment
    cached = data.get("apps_environment_id")
    if isinstance(cached, str) and cached:
        return cached
    environment = resolve_environment_id_from_context(ctx, None)
    data["apps_environment_id"] = environment
    return environment


@env_app.callback(invoke_without_command=True)
@handle_cli_errors
def env_root(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Power Platform API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    ctx.ensure_object(dict)["api_version"] = api_version
    if ctx.invoked_subcommand is None:
        list_envs(ctx, api_version=api_version)


@env_app.command("list")
@handle_cli_errors
def list_envs(
    ctx: typer.Context,
    api_version: str | None = typer.Option(
        None,
        help="Power Platform API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    """List Power Platform environments."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    envs = client.list_environments()
    for env in envs:
        print(f"[bold]{env.name or env.id}[/bold]  type={env.type}  location={env.location}")


@env_app.command("copy")
@handle_cli_errors
def copy_environment_command(
    ctx: typer.Context,
    payload: str | None = typer.Option(None, "--payload", help="JSON payload for the copy request."),
    environment_id: str | None = typer.Option(
        None, help="Source environment ID (defaults to profile configuration)"
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Copy an environment into a new target environment."""

    version = _ensure_api_version(ctx, api_version)
    env_id = resolve_environment_id_from_context(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx, api_version=version)
    handle = client.copy_environment(env_id, body)
    _print_operation_result("Environment copy", handle)


@env_app.command("reset")
@handle_cli_errors
def reset_environment_command(
    ctx: typer.Context,
    payload: str | None = typer.Option(None, "--payload", help="JSON payload for the reset request."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to reset (defaults to profile configuration)"
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Reset an environment to a previous state."""

    version = _ensure_api_version(ctx, api_version)
    env_id = resolve_environment_id_from_context(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx, api_version=version)
    handle = client.reset_environment(env_id, body)
    _print_operation_result("Environment reset", handle)


@env_app.command("backup")
@handle_cli_errors
def backup_environment_command(
    ctx: typer.Context,
    payload: str | None = typer.Option(None, "--payload", help="JSON payload for the backup request."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to backup (defaults to profile configuration)"
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Create a manual backup for an environment."""

    version = _ensure_api_version(ctx, api_version)
    env_id = resolve_environment_id_from_context(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx, api_version=version)
    handle = client.backup_environment(env_id, body)
    _print_operation_result("Environment backup", handle)


@env_app.command("restore")
@handle_cli_errors
def restore_environment_command(
    ctx: typer.Context,
    payload: str | None = typer.Option(None, "--payload", help="JSON payload for the restore request."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to restore (defaults to profile configuration)"
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Restore an environment from a backup."""

    version = _ensure_api_version(ctx, api_version)
    env_id = resolve_environment_id_from_context(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx, api_version=version)
    handle = client.restore_environment(env_id, body)
    _print_operation_result("Environment restore", handle)


@env_group_app.command("list")
@handle_cli_errors
def list_environment_groups(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """List all environment groups."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    groups = client.list_environment_groups()
    for group in groups:
        print(group)


@env_group_app.command("get")
@handle_cli_errors
def get_environment_group_command(
    ctx: typer.Context,
    group_id: str = typer.Argument(..., help="Environment group identifier."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Get details for a specific environment group."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    group = client.get_environment_group(group_id)
    print(group)


@env_group_app.command("create")
@handle_cli_errors
def create_environment_group_command(
    ctx: typer.Context,
    payload: str = typer.Option(..., "--payload", help="JSON payload describing the group."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Create a new environment group."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    body = _parse_payload(payload)
    result = client.create_environment_group(body)
    print(result)


@env_group_app.command("update")
@handle_cli_errors
def update_environment_group_command(
    ctx: typer.Context,
    group_id: str = typer.Argument(..., help="Environment group identifier."),
    payload: str = typer.Option(..., "--payload", help="JSON payload with updates."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Update an existing environment group."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    body = _parse_payload(payload)
    result = client.update_environment_group(group_id, body)
    print(result)


@env_group_app.command("delete")
@handle_cli_errors
def delete_environment_group_command(
    ctx: typer.Context,
    group_id: str = typer.Argument(..., help="Environment group identifier."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Delete an environment group."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    handle = client.delete_environment_group(group_id)
    _print_operation_result("Environment group delete", handle)


@env_group_app.command("apply")
@handle_cli_errors
def apply_environment_group_command(
    ctx: typer.Context,
    group_id: str = typer.Argument(..., help="Environment group identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to join to the group (defaults to profile configuration)"
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Apply an environment group to an environment."""

    version = _ensure_api_version(ctx, api_version)
    env_id = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    handle = client.apply_environment_group(group_id, env_id)
    _print_operation_result("Environment group apply", handle)


@env_group_app.command("revoke")
@handle_cli_errors
def revoke_environment_group_command(
    ctx: typer.Context,
    group_id: str = typer.Argument(..., help="Environment group identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to remove from the group (defaults to profile configuration)"
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    """Revoke an environment group from an environment."""

    version = _ensure_api_version(ctx, api_version)
    env_id = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    handle = client.revoke_environment_group(group_id, env_id)
    _print_operation_result("Environment group revoke", handle)


def _render_app_list(ctx: typer.Context, environment_id: str) -> None:
    client = _build_client(ctx)
    apps = client.list_apps(environment_id)
    for app_summary in apps:
        print(f"[bold]{app_summary.name or app_summary.id}[/bold]")


@apps_app.callback(invoke_without_command=True)
@handle_cli_errors
def apps_root(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        env_id = _resolve_app_environment(ctx, environment_id)
        _render_app_list(ctx, env_id)
    elif environment_id:
        _resolve_app_environment(ctx, environment_id)


@apps_app.command("list")
@handle_cli_errors
def list_apps(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
) -> None:
    """List canvas apps in an environment."""

    env_id = _resolve_app_environment(ctx, environment_id)
    _render_app_list(ctx, env_id)


@apps_app.command("versions")
@handle_cli_errors
def list_app_versions_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
    top: int | None = typer.Option(None, help="Maximum number of versions to return."),
    skiptoken: str | None = typer.Option(
        None, help="Continuation token returned by a previous call.",
    ),
) -> None:
    """List versions of a Power App."""

    env_id = _resolve_app_environment(ctx, environment_id)
    client = _build_client(ctx)
    page = client.list_app_versions(env_id, app_id, top=top, skiptoken=skiptoken)
    for version in page.versions:
        print(version.model_dump(exclude_none=True))
    if page.next_link:
        print(f"[yellow]nextLink[/yellow]: {page.next_link}")
    if page.continuation_token:
        print(f"[yellow]continuationToken[/yellow]: {page.continuation_token}")


@apps_app.command("restore")
@handle_cli_errors
def restore_app_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    version_id: str = typer.Option(..., "--version-id", help="Version identifier to restore."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
    target_environment_id: str | None = typer.Option(
        None, help="Environment ID to receive the restored app.",
    ),
    target_app_id: str | None = typer.Option(
        None, help="App ID to overwrite when restoring to another app.",
    ),
    target_app_name: str | None = typer.Option(
        None, help="Display name for a new app when creating one.",
    ),
    make_new_app: bool = typer.Option(
        False,
        "--make-new-app/--no-make-new-app",
        help="Create a new app instead of overwriting the source.",
    ),
) -> None:
    """Restore a Power App to a specific version."""

    env_id = _resolve_app_environment(ctx, environment_id)
    body: dict[str, Any] = {"restoreVersionId": version_id}
    if target_environment_id:
        body["targetEnvironmentId"] = target_environment_id
    if target_app_id:
        body["targetAppId"] = target_app_id
    if target_app_name:
        body["targetAppName"] = target_app_name
    if make_new_app:
        body["makeNewApp"] = True
    client = _build_client(ctx)
    handle = client.restore_app(env_id, app_id, body)
    _print_operation_result("App restore", handle)


@apps_app.command("publish")
@handle_cli_errors
def publish_app_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    version_id: str = typer.Option(..., "--version-id", help="Version to publish."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
    description: str | None = typer.Option(None, help="Optional release notes."),
) -> None:
    """Publish a Power App version."""

    env_id = _resolve_app_environment(ctx, environment_id)
    body: dict[str, Any] = {"versionId": version_id}
    if description:
        body["description"] = description
    client = _build_client(ctx)
    handle = client.publish_app(env_id, app_id, body)
    _print_operation_result("App publish", handle)


@apps_app.command("share")
@handle_cli_errors
def share_app_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing principals to share with.",
    ),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
) -> None:
    """Share an app with additional principals."""

    env_id = _resolve_app_environment(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx)
    handle = client.share_app(env_id, app_id, body)
    _print_operation_result("App share", handle)


@apps_app.command("revoke-share")
@handle_cli_errors
def revoke_app_share_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing principals to revoke.",
    ),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
) -> None:
    """Revoke shared access to an app."""

    env_id = _resolve_app_environment(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx)
    handle = client.revoke_app_share(env_id, app_id, body)
    _print_operation_result("App share revoke", handle)


@apps_app.command("permissions")
@handle_cli_errors
def list_app_permissions_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
) -> None:
    """List principals with access to a Power App."""

    env_id = _resolve_app_environment(ctx, environment_id)
    client = _build_client(ctx)
    permissions = client.list_app_permissions(env_id, app_id)
    for assignment in permissions:
        summary = assignment.model_dump(exclude_none=True)
        print(summary)


@apps_app.command("set-owner")
@handle_cli_errors
def set_app_owner_command(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="App identifier."),
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing the new owner.",
    ),
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)",
    ),
) -> None:
    """Assign a new owner for a Power App."""

    env_id = _resolve_app_environment(ctx, environment_id)
    body = _parse_payload(payload)
    client = _build_client(ctx)
    handle = client.set_app_owner(env_id, app_id, body)
    _print_operation_result("App owner update", handle)


def register(app: typer.Typer) -> None:
    app.add_typer(env_app, name="env")
    app.add_typer(env_group_app, name="env-group")
    app.add_typer(apps_app, name="apps")
    app.command("flows")(list_flows)


@handle_cli_errors
@handle_cli_errors
def list_flows(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
) -> None:
    """List cloud flows in an environment."""

    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = _build_client(ctx)
    flows = client.list_cloud_flows(environment)
    for flow in flows:
        print(f"[bold]{flow.name or flow.id}[/bold]")


__all__ = [
    "register",
    "list_envs",
    "list_apps",
    "apps_root",
    "list_app_versions_command",
    "restore_app_command",
    "publish_app_command",
    "share_app_command",
    "revoke_app_share_command",
    "list_app_permissions_command",
    "set_app_owner_command",
    "list_flows",
    "copy_environment_command",
    "reset_environment_command",
    "backup_environment_command",
    "restore_environment_command",
    "list_environment_groups",
    "get_environment_group_command",
    "create_environment_group_command",
    "update_environment_group_command",
    "delete_environment_group_command",
    "apply_environment_group_command",
    "revoke_environment_group_command",
]

PowerPlatformClient = _DefaultPowerPlatformClient
