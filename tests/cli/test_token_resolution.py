from __future__ import annotations

import importlib
import sys
import types

import pytest

from pacx.config import ConfigData, Profile
from pacx.errors import AuthError


def load_common_module():
    sys.modules.pop("pacx.cli.common", None)
    return importlib.import_module("pacx.cli.common")


def make_config(profile: Profile) -> ConfigData:
    return ConfigData(default_profile=profile.name, profiles={profile.name: profile})


def test_token_resolution_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "env-token")

    profile = Profile(
        name="default",
        tenant_id="tenant",
        client_id="client",
        scope="https://api.powerplatform.com/.default",
    )
    config = make_config(profile)

    common = load_common_module()

    getter = common.resolve_token_getter(config=config)

    assert getter() == "env-token"

    # Subsequent calls should continue to honour the runtime environment override.
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "updated-env-token")
    assert getter() == "updated-env-token"


def test_token_resolution_prefers_keyring_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    profile = Profile(
        name="default",
        tenant_id="tenant",
        client_id="client",
        scope="https://api.powerplatform.com/.default",
    )
    profile.token_backend = "keyring"
    profile.token_ref = "svc:user"
    config = make_config(profile)

    common = load_common_module()

    calls: list[str] = []

    def fake_get_secret(spec):
        calls.append(f"{spec.backend}:{spec.ref}")
        return "keyring-token"

    monkeypatch.setattr(common, "get_secret", fake_get_secret)

    getter = common.resolve_token_getter(config=config)

    assert getter() == "keyring-token"
    assert calls == ["keyring:svc:user"]


def test_token_resolution_uses_cached_config_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    profile = Profile(
        name="default",
        tenant_id="tenant",
        client_id="client",
        scope="https://api.powerplatform.com/.default",
        access_token="stored-token",
    )
    config = make_config(profile)

    common = load_common_module()

    getter = common.resolve_token_getter(config=config)

    assert getter() == "stored-token"

    profile.access_token = "rotated-token"
    assert getter() == "rotated-token"


def test_token_resolution_refresh_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    profile = Profile(
        name="default",
        tenant_id="tenant",
        client_id="client",
        scope="https://api.powerplatform.com/.default",
    )
    config = make_config(profile)

    common = load_common_module()

    saved_tokens: list[str] = []

    class StubStore:
        def add_or_update_profile(self, updated_profile: Profile, *, set_default: bool = False):
            if updated_profile.access_token:
                saved_tokens.append(updated_profile.access_token)
            return make_config(updated_profile)

    stub_store = StubStore()
    monkeypatch.setattr(common, "ConfigStore", lambda: stub_store)

    class RecordingProvider:
        def __init__(self, **kwargs) -> None:
            self.profile = kwargs["profile"]
            self.store_factory = kwargs["store_factory"]
            self.calls = 0

        def get_token(self) -> str:
            self.calls += 1
            token_value = f"provider-token-{self.calls}"
            self.profile.access_token = token_value
            store = self.store_factory()
            store.add_or_update_profile(self.profile)
            return token_value

    fake_module = types.ModuleType("pacx.auth.azure_ad")
    fake_module.AzureADTokenProvider = RecordingProvider
    monkeypatch.setitem(sys.modules, "pacx.auth.azure_ad", fake_module)

    getter = common.resolve_token_getter(config=config)

    first = getter()
    assert first == "provider-token-1"
    assert saved_tokens == ["provider-token-1"]

    saved_tokens.clear()
    second = getter()
    assert second == "provider-token-1"
    assert saved_tokens == []


def test_token_resolution_refresh_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    profile = Profile(
        name="default",
        tenant_id="tenant",
        client_id="client",
        scope="https://api.powerplatform.com/.default",
    )
    config = make_config(profile)

    common = load_common_module()

    class FailingProvider:
        def __init__(self, **kwargs) -> None:
            pass

        def get_token(self) -> str:
            raise AuthError("refresh failed")

    fake_module = types.ModuleType("pacx.auth.azure_ad")
    fake_module.AzureADTokenProvider = FailingProvider
    monkeypatch.setitem(sys.modules, "pacx.auth.azure_ad", fake_module)

    getter = common.resolve_token_getter(config=config)

    with pytest.raises(AuthError):
        getter()
