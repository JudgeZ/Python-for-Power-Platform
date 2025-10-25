from __future__ import annotations

"""Typer commands for interacting with the Power Platform REST APIs."""

from importlib import import_module
from typing import Type, cast

import typer
from rich import print

from ..cli_utils import resolve_environment_id_from_context
from ..clients.power_platform import PowerPlatformClient as _DefaultPowerPlatformClient
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


def register(app: typer.Typer) -> None:
    app.command("env")(list_envs)
    app.command("apps")(list_apps)
    app.command("flows")(list_flows)


@handle_cli_errors
def list_envs(
    ctx: typer.Context,
    api_version: str = typer.Option(
        "2022-03-01-preview",
        help="Power Platform API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    """List Power Platform environments.

    Args:
        ctx: Typer context providing authentication state.
        api_version: API version used to call the management endpoint.
    """
    token_getter = get_token_getter(ctx)
    client_cls = _resolve_client_class()
    client = client_cls(token_getter, api_version=api_version)
    envs = client.list_environments()
    for env in envs:
        print(f"[bold]{env.name or env.id}[/bold]  type={env.type}  location={env.location}")


@handle_cli_errors
def list_apps(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
) -> None:
    """List canvas apps in an environment.

    Args:
        ctx: Typer context providing authentication state.
        environment_id: Optional environment override.
    """

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client_cls = _resolve_client_class()
    client = client_cls(token_getter)
    apps = client.list_apps(environment)
    for app_summary in apps:
        print(f"[bold]{app_summary.name or app_summary.id}[/bold]")


@handle_cli_errors
def list_flows(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
) -> None:
    """List cloud flows in an environment.

    Args:
        ctx: Typer context providing authentication state.
        environment_id: Optional environment override.
    """

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client_cls = _resolve_client_class()
    client = client_cls(token_getter)
    flows = client.list_cloud_flows(environment)
    for flow in flows:
        print(f"[bold]{flow.name or flow.id}[/bold]")


__all__ = [
    "register",
    "list_envs",
    "list_apps",
    "list_flows",
]

PowerPlatformClient = _DefaultPowerPlatformClient
