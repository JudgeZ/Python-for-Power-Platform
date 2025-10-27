from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass

import pytest
import typer

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
def cli_app() -> typer.Typer:
    from pacx.cli import app

    return app


def test_device_flow_sets_device_code(cli_runner, cli_app, stub_store: StubStore) -> None:
    result = cli_runner.invoke(
        cli_app,
        [
            "auth",
            "create",
            "demo",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
        ],
    )
    assert result.exit_code == 0
    profile = stub_store.profiles["demo"]
    assert profile.use_device_code is True
    assert profile.scope == "https://api.powerplatform.com/.default"
    assert stub_store.default == "demo"
    assert "device code flow" in result.stdout


def test_web_flow_disables_device_code(cli_runner, cli_app, stub_store: StubStore) -> None:
    result = cli_runner.invoke(
        cli_app,
        [
            "auth",
            "create",
            "interactive",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
            "--flow",
            "web",
            "--scope",
            "https://graph.microsoft.com/.default https://api.powerplatform.com/.default",
        ],
    )
    assert result.exit_code == 0
    profile = stub_store.profiles["interactive"]
    assert profile.use_device_code is False
    assert profile.scopes == [
        "https://graph.microsoft.com/.default",
        "https://api.powerplatform.com/.default",
    ]
    assert stub_store.default == "interactive"
    assert "interactive browser flow" in result.stdout


def test_client_credentials_uses_secret_hints(cli_runner, cli_app, stub_store: StubStore) -> None:
    result = cli_runner.invoke(
        cli_app,
        [
            "auth",
            "create",
            "svc",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
            "--flow",
            "client-credential",
            "--client-secret-env",
            "SERVICE_SECRET",
            "--secret-backend",
            "keyvault",
            "--secret-ref",
            "https://vault.vault.azure.net:secret-name",
        ],
    )
    assert result.exit_code == 0
    profile = stub_store.profiles["svc"]
    assert profile.use_device_code is False
    assert profile.client_secret_env == "SERVICE_SECRET"  # noqa: S105
    assert profile.secret_backend == "keyvault"  # noqa: S105
    assert profile.secret_ref == "https://vault.vault.azure.net:secret-name"  # noqa: S105
    assert "client credentials via keyvault" in result.stdout


def test_no_set_default_respects_existing_default(
    cli_runner, cli_app, stub_store: StubStore
) -> None:
    stub_store.profiles["existing"] = Profile(
        name="existing",
        tenant_id="t",
        client_id="c",
        scope="https://api.powerplatform.com/.default",
    )
    stub_store.default = "existing"

    result = cli_runner.invoke(
        cli_app,
        [
            "auth",
            "create",
            "secondary",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
            "--no-set-default",
        ],
    )
    assert result.exit_code == 0
    assert stub_store.default == "existing"
    assert "Default profile not modified" in result.stdout
