from __future__ import annotations
from pacx.config import upsert_profile, list_profiles, get_profile, set_default_profile, get_default_profile_name, Profile
import os

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
