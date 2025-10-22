from __future__ import annotations

from pacx.config import ConfigStore, Profile


def test_profile_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PACX_HOME", str(tmp_path / ".pacx"))
    store = ConfigStore()

    profile = Profile(
        name="dev",
        tenant_id="tid",
        client_id="cid",
        dataverse_host="host",
        scope="s1",
        access_token="tok",
        client_secret_env="PACX_SECRET",
        secret_backend="env",
        secret_ref="ENV:DEV",
    )

    store.add_or_update_profile(profile, set_default=True)

    assert store.list_profiles() == ["dev"]
    assert store.get_default_profile_name() == "dev"

    cfg = store.load()
    loaded = cfg.profiles["dev"]
    assert loaded.client_id == "cid"
    assert loaded.scope == "s1"
    assert loaded.scopes == ["s1"]
    assert loaded.client_secret_env == "PACX_SECRET"
    assert loaded.secret_backend == "env"
    assert loaded.secret_ref == "ENV:DEV"
    assert store.get_token_for_profile("dev") == "tok"

    store.set_default_profile("dev")
    assert store.get_default_profile_name() == "dev"
