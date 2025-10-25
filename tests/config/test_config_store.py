from __future__ import annotations

import json
from pathlib import Path

import pytest

import pacx.config as config_module
from pacx.config import ConfigData, ConfigStore, Profile


def _reset_cipher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module, "_cached_cipher", None, raising=False)
    monkeypatch.setattr(config_module, "_cached_cipher_key", None, raising=False)


def test_load_legacy_profile_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    legacy_payload = {
        "default": "legacy",
        "profiles": {
            "legacy": {
                "name": "legacy",
                "tenant_id": "tenant",
                "client_id": "client",
                "scope": "scope-value",
                "unknown_field": "ignored",
            }
        },
    }
    path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    store = ConfigStore(path=path)
    cfg = store.load()

    profile = cfg.profiles["legacy"]
    assert profile.scope == "scope-value"
    assert profile.refresh_token is None
    assert profile.use_device_code is False
    assert "unknown_field" not in profile.__dict__


def test_encryption_round_trip_covers_refresh_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("cryptography", reason="cryptography required")
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("PACX_CONFIG_ENCRYPTION_KEY", key)
    _reset_cipher(monkeypatch)

    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    profile = Profile(
        name="secure",
        access_token="access-token",  # noqa: S106
        refresh_token="refresh-token",  # noqa: S106
    )
    cfg = ConfigData(default_profile="secure", profiles={"secure": profile})

    store.save(cfg)

    raw = json.loads(path.read_text(encoding="utf-8"))
    stored_profile = raw["profiles"]["secure"]
    assert stored_profile["access_token"].startswith("enc:")
    assert stored_profile["refresh_token"].startswith("enc:")

    loaded = store.load()
    secure_profile = loaded.profiles["secure"]
    assert secure_profile.access_token == "access-token"  # noqa: S105
    assert secure_profile.refresh_token == "refresh-token"  # noqa: S105
