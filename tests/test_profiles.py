# ruff: noqa: S101,S105,S106 - tests rely on ``assert`` and sample secrets
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from pacx.config import (
    ConfigData,
    ConfigStore,
    Profile,
    get_default_profile_name,
    get_profile,
    list_profiles,
    set_default_profile,
    upsert_profile,
)


def test_profile_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_config_store_profile_ops(tmp_path: Path) -> None:
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


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permissions semantics")
def test_config_store_sets_restrictive_permissions(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.save(ConfigData())

    mode = stat.S_IMODE(cfg_path.stat().st_mode)
    assert mode & stat.S_IRUSR
    assert mode & stat.S_IWUSR
    assert (mode & 0o077) == 0

    # Simulate accidental chmod 0644 and ensure load corrects it.
    os.chmod(cfg_path, 0o644)
    assert stat.S_IMODE(cfg_path.stat().st_mode) == 0o644
    store.load()
    mode_after = stat.S_IMODE(cfg_path.stat().st_mode)
    assert (mode_after & 0o077) == 0


def test_config_store_encrypts_tokens(tmp_path: Path) -> None:
    fernet_mod = pytest.importorskip("cryptography.fernet")
    key = fernet_mod.Fernet.generate_key()

    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path, encryption_key=key)
    profile = Profile(name="secure", access_token="super-secret")
    store.add_or_update_profile(profile, set_default=True)

    raw = json.loads(cfg_path.read_text("utf-8"))
    stored = raw["profiles"]["secure"]["access_token"]
    assert isinstance(stored, dict)
    assert stored.get("encrypted") == "fernet"
    assert stored.get("value") != "super-secret"

    loaded = store.load()
    loaded_profile = loaded.profiles["secure"]
    assert loaded_profile.access_token == "super-secret"
    assert loaded_profile.encrypted_access_token == stored["value"]


def test_config_store_replaces_encrypted_token_when_encryption_disabled(
    tmp_path: Path,
) -> None:
    fernet_mod = pytest.importorskip("cryptography.fernet")
    key = fernet_mod.Fernet.generate_key()

    cfg_path = tmp_path / "config.json"
    encrypted_store = ConfigStore(path=cfg_path, encryption_key=key)
    encrypted_store.add_or_update_profile(
        Profile(name="secure", access_token="first-secret"),
        set_default=True,
    )

    initial_raw = json.loads(cfg_path.read_text("utf-8"))
    initial_payload = initial_raw["profiles"]["secure"]
    initial_encrypted = initial_payload["access_token"]["value"]

    plaintext_store = ConfigStore(path=cfg_path)
    cfg = plaintext_store.load()
    profile = cfg.profiles["secure"]
    # Simulate user providing a replacement token while encryption is unavailable.
    profile.access_token = "replacement-token"
    plaintext_store.save(cfg)

    updated_raw = json.loads(cfg_path.read_text("utf-8"))
    updated_payload = updated_raw["profiles"]["secure"]
    stored_token = updated_payload["access_token"]

    assert isinstance(stored_token, str)
    assert stored_token == "replacement-token"
    assert stored_token != initial_encrypted
    assert "encrypted_access_token" not in updated_payload
    # ConfigData profile should no longer carry the stale encrypted token.
    assert cfg.profiles["secure"].encrypted_access_token is None
