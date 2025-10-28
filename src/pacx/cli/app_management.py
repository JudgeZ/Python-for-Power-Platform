from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import typer
from rich import print

from ..clients.app_management import DEFAULT_API_VERSION
from ..clients.app_management import (
    AppManagementClient as _DefaultAppManagementClient,
)
from ..clients.power_apps_admin import AdminOperationHandle, PowerAppsAdminClient
from ..models.app_management import ApplicationPackageOperation, ApplicationPackageSummary
from ..models.power_platform import (
    AppListPage,
    AppSummary,
    RevokeShareRequest,
    SetOwnerRequest,
    ShareAppRequest,
    SharePrincipal,
)
from ..utils.poller import PollTimeoutError
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Manage Power Platform application packages.")
packages_app = typer.Typer(help="Manage application package lifecycle.")
app.add_typer(packages_app, name="pkgs")
admin_app = typer.Typer(help="Administer Power Apps within an environment.")
app.add_typer(admin_app, name="admin")


def _resolve_client_class() -> type[_DefaultAppManagementClient]:
    try:
        module = import_module("pacx.cli")
    except Exception:  # pragma: no cover - defensive fallback
        return _DefaultAppManagementClient

    client_cls = getattr(module, "AppManagementClient", None)
    if client_cls is None:
        return _DefaultAppManagementClient
    return cast(type[_DefaultAppManagementClient], client_cls) or _DefaultAppManagementClient


def _build_client(
    ctx: typer.Context,
    *,
    api_version: str | None = None,
) -> _DefaultAppManagementClient:
    token_getter = get_token_getter(ctx)
    client_cls = _resolve_client_class()
    if api_version is None:
        return client_cls(token_getter)
    return client_cls(token_getter, api_version=api_version)


def _build_admin_client(
    ctx: typer.Context,
    *,
    api_version: str,
) -> PowerAppsAdminClient:
    token_getter = get_token_getter(ctx)
    return PowerAppsAdminClient(token_getter, api_version=api_version)


def _ensure_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["api_version"] = override
        return override
    return cast(str, data.get("api_version", DEFAULT_API_VERSION))


def _parse_parameters(raw: str | None) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - option validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def _load_json_or_path(raw: str) -> Any:
    candidate = raw.strip()
    if not candidate:
        raise typer.BadParameter("Value cannot be empty.")
    path = Path(candidate[1:]) if candidate.startswith("@") else Path(candidate)
    if path.exists():
        return json.loads(path.read_text())
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON value: {exc}") from exc


def _render_package_line(package: ApplicationPackageSummary) -> str:
    name = package.display_name or package.unique_name or package.package_id or "<unknown>"
    parts = [f"[bold]{name}[/bold]"]
    if package.package_id:
        parts.append(f"id={package.package_id}")
    if package.environment_id:
        parts.append(f"environment={package.environment_id}")
    if package.version:
        parts.append(f"version={package.version}")
    if package.install_state:
        parts.append(f"state={package.install_state}")
    return "  ".join(parts)


_FAILED_STATUSES = frozenset({"failed", "canceled"})


def _print_operation(
    action: str,
    result: ApplicationPackageOperation,
    *,
    fail_on_incomplete: bool = True,
) -> None:
    status = result.status or "Unknown"
    normalized = status.casefold()
    if normalized == "succeeded":
        print(f"[green]{action} completed[/green] status={status}")
    else:
        is_failure = normalized in _FAILED_STATUSES
        palette = "red" if is_failure else "yellow"
        stage = "failed" if is_failure else "in progress"
        print(f"[{palette}]{action} {stage}[/{palette}] status={status}")
        if is_failure or fail_on_incomplete:
            if result.operation_id:
                print(f"operation={result.operation_id}")
            if result.properties:
                print(result.properties)
            raise typer.Exit(1)
    if result.operation_id:
        print(f"operation={result.operation_id}")
    if result.properties:
        print(result.properties)


@app.callback()
def set_default_version(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Power Platform API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    ctx.ensure_object(dict)["api_version"] = api_version


@packages_app.command("list")
@handle_cli_errors
def list_packages(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None,
        "--environment-id",
        "-e",
        help="Environment ID to scope the list to.",
    ),
    api_version: str | None = typer.Option(
        None,
        "--api-version",
        help="Power Platform API version override.",
    ),
) -> None:
    """List application packages."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    packages: list[ApplicationPackageSummary]
    if environment_id:
        packages = client.list_environment_packages(environment_id)
    else:
        packages = client.list_tenant_packages()
    for pkg in packages:
        print(_render_package_line(pkg))


@packages_app.command("install")
@handle_cli_errors
def install_package(
    ctx: typer.Context,
    package_id: str = typer.Argument(..., help="Application package identifier."),
    environment_id: str = typer.Option(
        ..., "--environment-id", "-e", help="Environment ID where the package will be installed."
    ),
    parameters: str | None = typer.Option(
        None,
        "--parameters",
        help="Optional JSON payload of install parameters.",
    ),
    api_version: str | None = typer.Option(
        None,
        "--api-version",
        help="Power Platform API version override.",
    ),
    interval: float = typer.Option(2.0, help="Polling interval in seconds."),
    timeout: float = typer.Option(600.0, help="Polling timeout in seconds."),
) -> None:
    """Install an application package and wait for completion."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    payload = _parse_parameters(parameters)
    handle = client.install_application_package(package_id, environment_id, parameters=payload)
    try:
        result = client.wait_for_operation(
            handle,
            environment_id=environment_id,
            interval=interval,
            timeout=timeout,
        )
    except PollTimeoutError as exc:
        print(f"[red]Install timed out after {exc.timeout} seconds[/red]")
        raise typer.Exit(1) from None
    _print_operation("Install", result)


@packages_app.command("upgrade")
@handle_cli_errors
def upgrade_package(
    ctx: typer.Context,
    environment_id: str = typer.Option(
        ..., "--environment-id", "-e", help="Environment ID containing the package."
    ),
    package_id: str = typer.Argument(..., help="Installed package identifier to upgrade."),
    payload: str | None = typer.Option(
        None,
        "--payload",
        help="Optional JSON payload describing upgrade parameters.",
    ),
    api_version: str | None = typer.Option(
        None,
        "--api-version",
        help="Power Platform API version override.",
    ),
    interval: float = typer.Option(2.0, help="Polling interval in seconds."),
    timeout: float = typer.Option(600.0, help="Polling timeout in seconds."),
) -> None:
    """Upgrade an installed application package."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    body = _parse_parameters(payload)
    handle = client.upgrade_environment_package(environment_id, package_id, payload=body)
    try:
        result = client.wait_for_operation(
            handle,
            environment_id=environment_id,
            interval=interval,
            timeout=timeout,
        )
    except PollTimeoutError as exc:
        print(f"[red]Upgrade timed out after {exc.timeout} seconds[/red]")
        raise typer.Exit(1) from None
    _print_operation("Upgrade", result)


@packages_app.command("status")
@handle_cli_errors
def get_status(
    ctx: typer.Context,
    operation_id: str = typer.Argument(
        ..., help="Operation identifier returned from install or upgrade."
    ),
    environment_id: str | None = typer.Option(
        None,
        "--environment-id",
        "-e",
        help="Environment ID if the operation is scoped to an environment.",
    ),
    api_version: str | None = typer.Option(
        None,
        "--api-version",
        help="Power Platform API version override.",
    ),
) -> None:
    """Show the status of an application package operation."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, api_version=version)
    if environment_id:
        status = client.get_environment_operation_status(environment_id, operation_id)
    else:
        status = client.get_install_status(operation_id)
    if status is None:
        print("[red]No status information available[/red]")
        raise typer.Exit(1)
    _print_operation("Status", status, fail_on_incomplete=False)


# ----------------------- Admin commands -------------------------------------


def _render_admin_line(app_summary: AppSummary) -> str:
    name = app_summary.display_name or app_summary.name or app_summary.id or "<unknown>"
    parts = [f"[bold]{name}[/bold]"]
    if app_summary.id:
        parts.append(f"id={app_summary.id}")
    if app_summary.environment_id:
        parts.append(f"environment={app_summary.environment_id}")
    return "  ".join(parts)


def _admin_operation_output(action: str, handle: AdminOperationHandle) -> None:
    palette = "green" if handle.operation_location else "yellow"
    print(f"[{palette}]{action} accepted[/{palette}]")
    if handle.operation_location:
        print(f"operation={handle.operation_location}")
    if handle.retry_after is not None:
        print(f"retry_after={handle.retry_after}")


@admin_app.command("list")
@handle_cli_errors
def list_admin_apps(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID to query."),
    top: int | None = typer.Option(None, help="Maximum number of apps to return."),
    continuation_token: str | None = typer.Option(
        None, "--continuation-token", help="Continuation token from a previous response."
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    page: AppListPage = client.list_apps(
        environment_id,
        top=top,
        continuation_token=continuation_token,
    )
    for summary in page.value:
        print(_render_admin_line(summary))
    if page.continuation_token:
        print(f"[yellow]Continuation token:[/yellow] {page.continuation_token}")


@admin_app.command("show")
@handle_cli_errors
def show_admin_app(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    summary = client.get_app(environment_id, app_id)
    print(summary.model_dump(by_alias=True, exclude_none=True))


@admin_app.command("versions")
@handle_cli_errors
def list_app_versions(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    top: int | None = typer.Option(None, help="Maximum number of versions to return."),
    continuation_token: str | None = typer.Option(
        None, "--continuation-token", help="Continuation token returned by the service."
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    page = client.list_app_versions(
        environment_id, app_id, top=top, continuation_token=continuation_token
    )
    for item in page.value:
        descriptor = item.description or ""
        identifier = item.version_id or item.id or "<unknown>"
        print(f"{identifier} {descriptor}".strip())
    if page.continuation_token:
        print(f"[yellow]Continuation token:[/yellow] {page.continuation_token}")


@admin_app.command("restore")
@handle_cli_errors
def restore_admin_app(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    payload: str = typer.Option(..., help="JSON string or @file describing the restore request."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    data = _load_json_or_path(payload)
    if not isinstance(data, dict):
        raise typer.BadParameter("Restore payload must be a JSON object.")
    handle = client.restore_app(environment_id, app_id, data)
    _admin_operation_output("Restore", handle)


@admin_app.command("publish")
@handle_cli_errors
def publish_admin_app(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    payload: str = typer.Option(..., help="JSON string or @file describing the publish request."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    data = _load_json_or_path(payload)
    if not isinstance(data, dict):
        raise typer.BadParameter("Publish payload must be a JSON object.")
    handle = client.publish_app(environment_id, app_id, data)
    _admin_operation_output("Publish", handle)


@admin_app.command("share")
@handle_cli_errors
def share_admin_app(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    principals: str = typer.Option(
        ...,
        "--principals",
        help="JSON array or @file containing principals to share with. Accepts objects with 'principals' and optional 'notifyShareTargets'.",
    ),
    notify: bool | None = typer.Option(
        None,
        "--notify",
        help="Override whether to send share notifications.",
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    decoded = _load_json_or_path(principals)
    payload_notify: bool | None = None
    if isinstance(decoded, dict) and "principals" in decoded:
        principal_objs = decoded.get("principals", [])
        payload_notify = decoded.get("notifyShareTargets")
    elif isinstance(decoded, list):
        principal_objs = decoded
    else:
        raise typer.BadParameter("Expected principals JSON array or object with 'principals'.")
    principal_list = PowerAppsAdminClient.share_principals_from_dict(principal_objs or [])
    if not principal_list:
        raise typer.BadParameter("No valid principals supplied.")
    request = ShareAppRequest(principals=principal_list)
    selected_notify = notify if notify is not None else payload_notify
    if selected_notify is not None:
        request.notify_share_targets = selected_notify
    handle = client.share_app(environment_id, app_id, request)
    _admin_operation_output("Share", handle)


@admin_app.command("revoke")
@handle_cli_errors
def revoke_access(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    principal_ids: str = typer.Option(
        ...,
        "--principal-ids",
        help="JSON array or @file containing principal GUIDs to revoke. Accepts objects with 'principalIds' and optional 'notifyShareTargets'.",
    ),
    notify: bool | None = typer.Option(
        None,
        "--notify",
        help="Override whether to send revoke notifications.",
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    decoded = _load_json_or_path(principal_ids)
    if isinstance(decoded, dict) and "principalIds" in decoded:
        ids = decoded.get("principalIds", [])
        payload_notify = decoded.get("notifyShareTargets")
    else:
        ids = decoded
        payload_notify = None
    if not isinstance(ids, list) or not ids:
        raise typer.BadParameter("Principal IDs must be provided as a non-empty JSON array.")
    request = RevokeShareRequest.model_validate({"principalIds": [str(value) for value in ids]})
    selected_notify = notify if notify is not None else payload_notify
    if selected_notify is not None:
        request.notify_share_targets = selected_notify
    handle = client.revoke_share(environment_id, app_id, request)
    _admin_operation_output("Revoke", handle)


@admin_app.command("set-owner")
@handle_cli_errors
def set_admin_owner(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    owner: str = typer.Option(
        ...,
        "--owner",
        help="JSON object or @file describing the new owner principal. Accepts objects with 'owner' and optional 'keepExistingOwnerAsCoOwner'.",
    ),
    keep_existing: bool | None = typer.Option(
        None,
        "--keep-existing",
        help="Override whether to keep the previous owner as co-owner.",
    ),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    decoded = _load_json_or_path(owner)
    if isinstance(decoded, dict) and "owner" in decoded:
        owner_payload = decoded.get("owner")
        payload_keep = decoded.get("keepExistingOwnerAsCoOwner")
    else:
        owner_payload = decoded
        payload_keep = None
    if not isinstance(owner_payload, dict):
        raise typer.BadParameter("Owner payload must be a JSON object.")
    principal = SharePrincipal.model_validate(owner_payload)
    request = SetOwnerRequest(owner=principal)
    selected_keep = keep_existing if keep_existing is not None else payload_keep
    if selected_keep is not None:
        request.keep_existing_owner_as_co_owner = selected_keep
    handle = client.set_owner(environment_id, app_id, request)
    _admin_operation_output("Set owner", handle)


@admin_app.command("permissions")
@handle_cli_errors
def list_admin_permissions(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment ID."),
    app_id: str = typer.Argument(..., help="App identifier."),
    api_version: str | None = typer.Option(None, help="Power Platform API version override."),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    client = _build_admin_client(ctx, api_version=version)
    assignments = client.list_permissions(environment_id, app_id)
    for assignment in assignments:
        print(assignment.model_dump(by_alias=True, exclude_none=True))


__all__ = ["app", "packages_app", "admin_app"]


AppManagementClient = _DefaultAppManagementClient
