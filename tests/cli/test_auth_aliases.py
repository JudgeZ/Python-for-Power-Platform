from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass

import pytest

from pacx.config import ConfigData, Profile


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

    def set_default_profile(self, name: str) -> None:
        self.default = name


@pytest.fixture(autouse=True)
def reload_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = [name for name in sys.modules if name.startswith("pacx.cli")]
    for module in modules:
        sys.modules.pop(module)
    importlib.import_module("pacx.cli")


@pytest.fixture
def stub_store(monkeypatch: pytest.MonkeyPatch) -> StubStore:
    store = StubStore()
    monkeypatch.setattr("pacx.cli.auth.ConfigStore", lambda: store)
    return store


@pytest.fixture
def cli_app():
    from pacx.cli import app

    return app


def test_device_alias_warns(cli_runner, cli_app, stub_store: StubStore) -> None:
    result = cli_runner.invoke(
        cli_app,
        [
            "auth",
            "device",
            "legacy",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
        ],
    )
    assert result.exit_code == 0
    assert "Deprecated" in result.stdout
    profile = stub_store.profiles["legacy"]
    assert profile.use_device_code is True
    assert stub_store.default == "legacy"


def test_client_alias_warns_and_prompts(
    monkeypatch: pytest.MonkeyPatch, cli_runner, cli_app, stub_store: StubStore
) -> None:
    class StubKeyring:
        def __init__(self) -> None:
            self.stored: list[tuple[str, str, str]] = []

        def set_password(self, service: str, username: str, secret: str) -> None:
            self.stored.append((service, username, secret))

    stub_keyring = StubKeyring()
    monkeypatch.setitem(sys.modules, "keyring", stub_keyring)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "super-secret")

    result = cli_runner.invoke(
        cli_app,
        [
            "auth",
            "client",
            "legacy-client",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
            "--secret-backend",
            "keyring",
            "--secret-ref",
            "svc:user",
            "--prompt-secret",
        ],
    )
    assert result.exit_code == 0
    assert "Deprecated" in result.stdout
    profile = stub_store.profiles["legacy-client"]
    assert profile.secret_backend == "keyring"  # noqa: S105
    assert profile.secret_ref == "svc:user"  # noqa: S105
    assert stub_keyring.stored == [("svc", "user", "super-secret")]
    assert stub_store.default == "legacy-client"


def test_auth_use_sets_default(cli_runner, cli_app, stub_store: StubStore) -> None:
    result = cli_runner.invoke(cli_app, ["auth", "use", "profile-a"])
    assert result.exit_code == 0
    assert stub_store.default == "profile-a"
