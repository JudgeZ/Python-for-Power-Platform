from __future__ import annotations

# ruff: noqa: S101,S103,S105,S106
import json
import os
import stat

import pytest

from pacx.config import (
    ConfigEncryptionError,
    ConfigStore,
    Profile,
    _clear_cached_encryption,
    get_default_profile_name,
    get_profile,
    list_profiles,
    load_config,
    set_default_profile,
    upsert_profile,
)


def test_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path / ".pacx"))
    p = Profile(
        name="dev",
        tenant_id="tid",
        client_id="cid",
        dataverse_host="host",
        scopes=["s1"],
        access_token="tok",
    )
    upsert_profile(p, set_default=True)
    assert list_profiles() == ["dev"]
    assert get_default_profile_name() == "dev"
    got = get_profile("dev")
    assert got and got.client_id == "cid"
    set_default_profile("dev")
    assert get_default_profile_name() == "dev"


def test_config_store_profile_ops(tmp_path):
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    profile = Profile(name="qa", tenant_id="tenant", client_id="client")

    cfg = store.add_or_update_profile(profile)
    assert cfg.default_profile == "qa"
    assert "qa" in cfg.profiles and cfg.profiles["qa"].client_id == "client"

    store.set_default_profile("qa")
    cfg = store.load()
    assert cfg.default_profile == "qa"

    with pytest.raises(KeyError):
        store.set_default_profile("missing")


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
def test_config_file_permissions_are_restricted(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path / ".pacx"))
    _clear_cached_encryption()
    profile = Profile(name="dev", access_token="tok")
    upsert_profile(profile, set_default=True)

    config_path = tmp_path / ".pacx" / "config.json"
    mode = stat.S_IMODE(config_path.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR

    os.chmod(config_path, 0o666)
    from pacx import config as config_module

    config_module.load_config()
    mode_after = stat.S_IMODE(config_path.stat().st_mode)
    assert mode_after == stat.S_IRUSR | stat.S_IWUSR


def test_encryption_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path / ".pacx"))
    monkeypatch.setenv("PACX_CONFIG_ENCRYPTION_KEY", "unit-test-key")
    _clear_cached_encryption()

    profile = Profile(name="secure", access_token="top-secret")
    upsert_profile(profile, set_default=True)

    config_path = tmp_path / ".pacx" / "config.json"
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    stored = raw["profiles"]["secure"]["access_token"]
    assert isinstance(stored, dict)
    assert stored.get("__pacx_encrypted__") is True

    config_data = load_config()
    assert config_data["profiles"]["secure"]["access_token"] == "top-secret"

    store = ConfigStore(path=config_path)
    cfg = store.load()
    assert cfg.profiles["secure"].access_token == "top-secret"


def test_encrypted_config_requires_key(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path / ".pacx"))
    monkeypatch.setenv("PACX_CONFIG_ENCRYPTION_KEY", "unit-test-key")
    _clear_cached_encryption()

    upsert_profile(Profile(name="secure", access_token="secret"), set_default=True)

    monkeypatch.delenv("PACX_CONFIG_ENCRYPTION_KEY")
    _clear_cached_encryption()

    with pytest.raises(ConfigEncryptionError):
        load_config()
