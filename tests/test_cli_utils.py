from __future__ import annotations

# ruff: noqa: S101
import pytest
import typer

import pacx.config as config_module
from pacx import config
from pacx.cli_utils import resolve_dataverse_host, resolve_environment_id


def test_resolve_environment_id_prefers_option(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False
    )
    store = config.ConfigStore()
    cfg = store.load()
    cfg.environment_id = "DEFAULT"
    store.save(cfg)

    assert resolve_environment_id("EXPLICIT") == "EXPLICIT"
    assert resolve_environment_id(None) == "DEFAULT"


def test_resolve_environment_id_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False
    )
    with pytest.raises(typer.BadParameter) as exc:
        resolve_environment_id(None)
    assert "profile set-env" in str(exc.value)


def test_resolve_dataverse_host_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False
    )
    monkeypatch.setenv("DATAVERSE_HOST", "env.example")
    assert resolve_dataverse_host(None) == "env.example"


def test_resolve_dataverse_host_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False
    )
    with pytest.raises(typer.BadParameter) as exc:
        resolve_dataverse_host(None)
    assert "DATAVERSE_HOST" in str(exc.value)
