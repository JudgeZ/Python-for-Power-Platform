from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import Any

import pytest
import typer

from pacx.config import ConfigData, Profile


@pytest.fixture(autouse=True)
def reload_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = [name for name in sys.modules if name.startswith("pacx.cli")]
    for module in modules:
        sys.modules.pop(module)
    importlib.import_module("pacx.cli")


@pytest.fixture
def cli_app() -> typer.Typer:
    from pacx.cli import app

    return app


@dataclass
class StubStore:
    profiles: dict[str, Profile]
    default: str | None

    def __init__(self) -> None:
        self.profiles = {}
        self.default = None

    def load(self) -> ConfigData:
        return ConfigData(default_profile=self.default, profiles=dict(self.profiles))

    def add_or_update_profile(self, profile: Profile, *, set_default: bool = False) -> ConfigData:
        self.profiles[profile.name] = profile
        if set_default or self.default is None:
            self.default = profile.name
        return self.load()


def test_login_help_mentions_alias(cli_runner: Any, cli_app: typer.Typer) -> None:
    result = cli_runner.invoke(cli_app, ["login", "--help"])
    assert result.exit_code == 0
    assert "Alias for 'auth create'" in result.stdout


def test_login_alias_forwards_to_auth_create(
    monkeypatch: pytest.MonkeyPatch, cli_runner: Any, cli_app: typer.Typer
) -> None:
    store = StubStore()
    # auth_create persists via ConfigStore inside pacx.cli.auth
    monkeypatch.setattr("pacx.cli.auth.ConfigStore", lambda: store)

    result = cli_runner.invoke(
        cli_app,
        [
            "login",
            "demo",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
        ],
    )

    assert result.exit_code == 0
    assert store.default == "demo"
    assert "Forwarding to 'ppx auth create'" in result.stdout
