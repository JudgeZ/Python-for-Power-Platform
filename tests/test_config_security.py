from __future__ import annotations

# ruff: noqa: S101,S105,S106
import json
import stat
import sys
from pathlib import Path

import pytest

import pacx.config as config_module
from pacx.config import ConfigData, ConfigStore, Profile, load_config, save_config


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission semantics")
def test_save_enforces_restrictive_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(Path(tmp_path) / "config.json"), raising=False
    )
    store = ConfigStore()
    cfg = store.load()
    cfg.environment_id = "ENV"
    store.save(cfg)

    config_path = Path(tmp_path) / "config.json"
    assert config_path.exists()
    mode = stat.S_IMODE(config_path.stat().st_mode)
    assert mode == 0o600


def test_encryption_round_trip(tmp_path, monkeypatch):
    pytest.importorskip("cryptography.fernet")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(Path(tmp_path) / "config.json"), raising=False
    )
    monkeypatch.setenv("PACX_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

    store = ConfigStore()
    profile = Profile(name="dev", access_token="token-value")
    cfg = ConfigData(default_profile="dev", profiles={"dev": profile})
    store.save(cfg)

    raw = json.loads((Path(tmp_path) / "config.json").read_text(encoding="utf-8"))
    assert raw["profiles"]["dev"]["access_token"].startswith("enc:")

    loaded = store.load()
    assert loaded.profiles["dev"].access_token == "token-value"


def test_encrypted_config_requires_key(tmp_path, monkeypatch):
    pytest.importorskip("cryptography.fernet")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(
        config_module, "CONFIG_PATH", str(Path(tmp_path) / "config.json"), raising=False
    )
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("PACX_CONFIG_ENCRYPTION_KEY", key)

    profile = Profile(name="dev", access_token="token-value")
    save_config({"default": "dev", "profiles": {"dev": profile.__dict__}})

    monkeypatch.delenv("PACX_CONFIG_ENCRYPTION_KEY")

    with pytest.raises(RuntimeError):
        load_config()
