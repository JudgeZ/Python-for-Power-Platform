from __future__ import annotations

import json
from importlib import import_module
from typing import Any, Type, cast

import typer
from rich import print

from ..clients.app_management import (
    DEFAULT_API_VERSION,
    AppManagementClient as _DefaultAppManagementClient,
)
from ..models.app_management import ApplicationPackageOperation, ApplicationPackageSummary
from ..utils.poller import PollTimeoutError
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Manage Power Platform application packages.")
packages_app = typer.Typer(help="Manage application package lifecycle.")
app.add_typer(packages_app, name="pkgs")


def _resolve_client_class() -> Type[_DefaultAppManagementClient]:
    try:
        module = import_module("pacx.cli")
    except Exception:  # pragma: no cover - defensive fallback
        return _DefaultAppManagementClient

    client_cls = getattr(module, "AppManagementClient", None)
    if client_cls is None:
        return _DefaultAppManagementClient
    return cast(Type[_DefaultAppManagementClient], client_cls) or _DefaultAppManagementClient


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


def _ensure_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["api_version"] = override
        return override
    return cast(str, data.get("api_version", DEFAULT_API_VERSION))


def _parse_parameters(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - option validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return cast(dict[str, Any], payload)


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
    operation_id: str = typer.Argument(..., help="Operation identifier returned from install or upgrade."),
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


__all__ = ["app", "packages_app"]


AppManagementClient = _DefaultAppManagementClient
