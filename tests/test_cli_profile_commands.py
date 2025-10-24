from __future__ import annotations

import importlib
import sys

import pytest
import typer

from pacx.cli.profile import MASK_PLACEHOLDER


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


class StubConfig:
    def __init__(self) -> None:
        self.default_profile: str | None = None
        self.profiles: dict[str, object] | None = {}
        self.environment_id: str | None = None
        self.dataverse_host: str | None = None


class StubStore:
    def __init__(self, cfg: StubConfig | None = None) -> None:
        self.cfg = cfg or StubConfig()
        self.saved: StubConfig | None = None

    def load(self) -> StubConfig:
        return self.cfg

    def save(self, cfg: StubConfig) -> None:
        self.saved = cfg


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app = load_cli_app(monkeypatch)
    store = StubStore()
    monkeypatch.setattr("pacx.cli.profile.ConfigStore", lambda: store)
    return app, store


def test_profile_list(cli_runner, cli_app) -> None:
    app, store = cli_app
    cfg = store.cfg
    cfg.profiles = {
        "default": object(),
        "other": object(),
    }
    cfg.default_profile = "default"

    result = cli_runner.invoke(app, ["profile", "list"])
    assert result.exit_code == 0
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines[0].startswith("*")
    assert any("other" in line for line in lines)


def test_profile_show(cli_runner, cli_app) -> None:
    import types

    app, store = cli_app
    token_value = "very-secret-token"
    store.cfg.profiles = {
        "named": types.SimpleNamespace(
            name="named", value=42, access_token=token_value
        )
    }

    result = cli_runner.invoke(app, ["profile", "show", "named"])
    assert result.exit_code == 0
    assert "value" in result.stdout
    assert MASK_PLACEHOLDER in result.stdout
    assert token_value not in result.stdout


def test_profile_show_missing(cli_runner, cli_app) -> None:
    app, _ = cli_app
    result = cli_runner.invoke(app, ["profile", "show", "missing"])
    assert result.exit_code != 0
    assert "Profile 'missing' not found" in result.stderr


def test_profile_setters(cli_runner, cli_app) -> None:
    app, store = cli_app
    env_result = cli_runner.invoke(app, ["profile", "set-env", "ENV123"])
    assert env_result.exit_code == 0
    assert store.saved is store.cfg
    assert store.cfg.environment_id == "ENV123"

    host_result = cli_runner.invoke(app, ["profile", "set-host", "example.crm"])
    assert host_result.exit_code == 0
    assert store.cfg.dataverse_host == "example.crm"
