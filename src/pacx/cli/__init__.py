from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast

import typer
from typer.models import CommandInfo

from . import (
    auth,
    connectors,
    dataverse,
    doctor,
    licensing,
    pages,
    power_platform,
    profile,
    solution,
)
from .auth import auth_create
from .licensing import LicensingClient
from .power_platform import PowerPlatformClient

app = typer.Typer(help="PACX CLI")


def _register_sub_app(name: str, sub_app: typer.Typer) -> None:
    app.add_typer(sub_app, name=name)


_register_sub_app("auth", auth.app)
_register_sub_app("profile", profile.app)
_register_sub_app("dv", dataverse.app)
_register_sub_app("connector", connectors.app)
_register_sub_app("licensing", licensing.app)
_register_sub_app("pages", pages.app)
_register_sub_app("solution", solution.app)


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


__all__ = [
    "app",
    "auth",
    "auth_create",
    "connectors",
    "dataverse",
    "doctor",
    "LicensingClient",
    "PowerPlatformClient",
    "pages",
    "licensing",
    "power_platform",
    "profile",
    "solution",
]
