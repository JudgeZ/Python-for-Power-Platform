from __future__ import annotations

# ruff: noqa: S101
import pytest
import typer
from typer.main import get_command

import pacx.config as config_module
from pacx import config
from pacx.cli_utils import (
    get_config_from_context,
    resolve_dataverse_host,
    resolve_dataverse_host_from_context,
    resolve_environment_id,
    resolve_environment_id_from_context,
)


def build_typer_context() -> typer.Context:
    """Return a minimal :class:`typer.Context` instance for CLI helpers."""

    command = get_command(typer.Typer())
    return typer.Context(command)


class DummyStore:
    def __init__(self, result: config.ConfigData | None = None) -> None:
        self.calls = 0
        self._result = result or config.ConfigData()

    def load(self) -> config.ConfigData:
        self.calls += 1
        return self._result


def test_resolve_environment_id_prefers_option(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False)
    store = config.ConfigStore()
    cfg = store.load()
    cfg.environment_id = "DEFAULT"
    store.save(cfg)

    assert resolve_environment_id("EXPLICIT") == "EXPLICIT"
    assert resolve_environment_id(None) == "DEFAULT"


def test_resolve_environment_id_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False)
    with pytest.raises(typer.BadParameter) as exc:
        resolve_environment_id(None)
    assert "profile set-env" in str(exc.value)


def test_resolve_dataverse_host_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False)
    monkeypatch.setenv("DATAVERSE_HOST", "env.example")
    assert resolve_dataverse_host(None) == "env.example"


def test_resolve_dataverse_host_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False)
    with pytest.raises(typer.BadParameter) as exc:
        resolve_dataverse_host(None)
    assert "DATAVERSE_HOST" in str(exc.value)


def test_get_config_from_context_caches() -> None:
    ctx = build_typer_context()
    store = DummyStore()
    cfg1 = get_config_from_context(ctx, store=store)
    cfg2 = get_config_from_context(ctx, store=store)
    assert cfg1 is cfg2
    assert store.calls == 1
    assert ctx.obj and ctx.obj["config"] is cfg1


def test_context_resolvers_use_cached_config() -> None:
    ctx = build_typer_context()
    config_data = config.ConfigData(environment_id="ENV123", dataverse_host="env.crm.dynamics.com")
    store = DummyStore(result=config_data)

    env_id = resolve_environment_id_from_context(ctx, None, store=store)
    host = resolve_dataverse_host_from_context(ctx, None, store=store)

    assert env_id == "ENV123"
    assert host == "env.crm.dynamics.com"
    assert store.calls == 1
