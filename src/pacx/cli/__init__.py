from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast

import typer
from typer.models import CommandInfo

from ..clients.user_management import UserManagementClient
from . import (
    analytics,
    app_management,
    auth,
    coe,
    connection,
    connectors,
    dataverse,
    doctor,
    environment,
    governance,
    licensing,
    pages,
    policy,
    power_automate,
    power_platform,
    profile,
    pva,
    solution,
    tenant,
    users,
)
from .app_management import AppManagementClient
from .auth import auth_create
from .licensing import LicensingClient
from .power_platform import PowerPlatformClient
from .pva import PVAClient

app = typer.Typer(help="PACX CLI")


def _register_sub_app(name: str, sub_app: typer.Typer) -> None:
    app.add_typer(sub_app, name=name)


_register_sub_app("app", app_management.app)
_register_sub_app("analytics", analytics.app)
_register_sub_app("auth", auth.app)
_register_sub_app("profile", profile.app)
_register_sub_app("dv", dataverse.app)
_register_sub_app("connection", connection.app)
_register_sub_app("connector", connectors.app)
_register_sub_app("policy", policy.app)
_register_sub_app("licensing", licensing.app)
_register_sub_app("pages", pages.app)
_register_sub_app("coe", coe.app)
_register_sub_app("pva", pva.app)
_register_sub_app("flows", power_automate.app)
_register_sub_app("environment", environment.app)
_register_sub_app("solution", solution.app)
_register_sub_app("governance", governance.app)
_register_sub_app("tenant", tenant.app)
_register_sub_app("users", users.app)


def _called_from_typer_main() -> bool:
    return any(frame.filename.endswith("typer/main.py") for frame in inspect.stack())


class _RegisteredCommandCollection:
    def __init__(
        self, base: list[CommandInfo], extras: Callable[[], Iterable[CommandInfo]]
    ) -> None:
        self._base = base
        self._extras_factory = extras

    def _extras(self) -> list[CommandInfo]:
        return list(self._extras_factory())

    def __iter__(self) -> Iterator[CommandInfo]:
        if _called_from_typer_main():
            return iter(self._base)
        combined = list(self._base) + self._extras()
        return iter(combined)

    def __len__(self) -> int:
        if _called_from_typer_main():
            return len(self._base)
        return len(self._base) + len(self._extras())

    def __getitem__(self, index: int) -> CommandInfo:
        data = list(self)  # relies on __iter__ to handle context
        return data[index]

    def append(self, value: CommandInfo) -> None:
        self._base.append(value)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


_base_registered_commands = app.registered_commands


def _extra_commands() -> Iterable[CommandInfo]:
    for info in app.registered_groups:
        yield CommandInfo(name=info.name, callback=lambda *args, **kwargs: None, help=info.help)


app.registered_commands = cast(
    list[CommandInfo],
    _RegisteredCommandCollection(_base_registered_commands, _extra_commands),
)

doctor.register(app)
power_platform.register(app)


@app.callback()
def common(ctx: typer.Context) -> None:
    """Initialize shared Typer context state."""

    ctx.ensure_object(dict)
    ctx.obj.setdefault("token_getter", None)


# ---- Aliases ---------------------------------------------------------------

from .auth import (  # noqa: E402  (import after app initialization)
    PROFILE_CLIENT_OPTION,
    PROFILE_CLIENT_SECRET_ENV_OPTION,
    PROFILE_DATAVERSE_OPTION,
    PROFILE_FLOW_OPTION,
    PROFILE_PROMPT_SECRET_OPTION,
    PROFILE_SCOPE_OPTION,
    PROFILE_SECRET_BACKEND_OPTION,
    PROFILE_SECRET_REF_OPTION,
    PROFILE_SET_DEFAULT_OPTION,
    PROFILE_TENANT_OPTION,
    FlowType,
)


@app.command("login", help="Alias for 'auth create' (routes to the same handler)")
def login(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = PROFILE_TENANT_OPTION,
    client_id: str = PROFILE_CLIENT_OPTION,
    scope: str = PROFILE_SCOPE_OPTION,
    flow: FlowType = PROFILE_FLOW_OPTION,
    dataverse_host: str | None = PROFILE_DATAVERSE_OPTION,
    client_secret_env: str | None = PROFILE_CLIENT_SECRET_ENV_OPTION,
    secret_backend: str | None = PROFILE_SECRET_BACKEND_OPTION,
    secret_ref: str | None = PROFILE_SECRET_REF_OPTION,
    prompt_secret: bool = PROFILE_PROMPT_SECRET_OPTION,
    set_default: bool = PROFILE_SET_DEFAULT_OPTION,
) -> None:
    """Forward to ``ppx auth create`` with the same options.

    This command is a thin alias to improve discoverability.
    """

    from . import auth as _auth  # local import to avoid circulars at import time

    typer.echo("[yellow]Alias:[/yellow] Forwarding to 'ppx auth create'.")
    _auth.auth_create(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scope=scope,
        flow=_ensure_flow(flow),
        dataverse_host=dataverse_host,
        client_secret_env=client_secret_env,
        secret_backend=secret_backend,
        secret_ref=secret_ref,
        prompt_secret=prompt_secret,
        set_default=set_default,
    )


def _ensure_flow(value: FlowType) -> FlowType:
    normalized = value.lower()
    if normalized not in {"device", "web", "client-credential"}:
        normalized = "device"
    return cast(FlowType, normalized)


__all__ = [
    "AppManagementClient",
    "analytics",
    "app",
    "auth",
    "auth_create",
    "app_management",
    "connectors",
    "dataverse",
    "doctor",
    "environment",
    "policy",
    "governance",
    "LicensingClient",
    "power_automate",
    "PowerPlatformClient",
    "pages",
    "licensing",
    "pva",
    "PVAClient",
    "power_platform",
    "profile",
    "solution",
    "tenant",
    "UserManagementClient",
    "users",
]
