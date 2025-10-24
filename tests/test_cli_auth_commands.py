from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass

import pytest
import typer


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


@dataclass
class StubStore:
    profiles: dict[str, object]
    default: str | None

    def __init__(self) -> None:
        self.profiles = {}
        self.default = None

    def add_or_update_profile(self, profile) -> None:  # pragma: no cover - interface shim
        self.profiles[profile.name] = profile

    def set_default_profile(self, name: str) -> None:
        self.default = name


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app = load_cli_app(monkeypatch)
    store = StubStore()
    monkeypatch.setattr("pacx.cli.auth.ConfigStore", lambda: store)
    return app, store


def test_auth_device_configures_profile(cli_runner, cli_app) -> None:
    app, store = cli_app
    result = cli_runner.invoke(
        app,
        [
            "auth",
            "device",
            "default",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
        ],
    )
    assert result.exit_code == 0
    profile = store.profiles.get("default")
    assert profile is not None
    assert profile.tenant_id == "tenant"
    assert store.default == "default"


def test_auth_client_keyring_prompt(monkeypatch: pytest.MonkeyPatch, cli_runner, cli_app) -> None:
    app, store = cli_app

    class StubKeyring:
        def __init__(self) -> None:
            self.stored: list[tuple[str, str, str]] = []

        def set_password(self, service: str, username: str, secret: str) -> None:
            self.stored.append((service, username, secret))

    stub_keyring = StubKeyring()
    monkeypatch.setitem(sys.modules, "keyring", stub_keyring)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "super-secret")

    result = cli_runner.invoke(
        app,
        [
            "auth",
            "client",
            "service",  # profile name
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
    profile = store.profiles.get("service")
    assert profile is not None
    # Bandit B105: backend identifier, not a secret.
    assert profile.secret_backend == "keyring"  # nosec B105
    # Bandit B105: reference to stored secret, not the secret itself.
    assert profile.secret_ref == "svc:user"  # nosec B105
    assert stub_keyring.stored == [("svc", "user", "super-secret")]
    assert store.default == "service"


def test_auth_client_keyvault_warning(cli_runner, cli_app) -> None:
    app, _ = cli_app
    result = cli_runner.invoke(
        app,
        [
            "auth",
            "client",
            "vault-profile",
            "--tenant-id",
            "tenant",
            "--client-id",
            "client",
            "--secret-backend",
            "keyvault",
        ],
    )
    assert result.exit_code == 0
    assert "Key Vault" in result.stdout


def test_auth_use_sets_default(cli_runner, cli_app) -> None:
    app, store = cli_app
    result = cli_runner.invoke(app, ["auth", "use", "profile-a"])
    assert result.exit_code == 0
    assert store.default == "profile-a"
