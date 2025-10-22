from __future__ import annotations
import os

import pytest

from pacx.config import (
    ConfigStore,
    Profile,
    get_default_profile_name,
    get_profile,
    list_profiles,
    set_default_profile,
    upsert_profile,
)

def test_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path / ".pacx"))
    p = Profile(name="dev", tenant_id="tid", client_id="cid", dataverse_host="host", scopes=["s1"], access_token="tok")
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
