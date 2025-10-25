from __future__ import annotations

import json
from pathlib import Path

import pytest

import pacx.config as config_module
from pacx.config import ConfigData, ConfigStore, Profile


def test_refresh_token_encryption_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("cryptography.fernet")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(config_path), raising=False)
    monkeypatch.setenv("PACX_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

    store = ConfigStore(path=config_path)
    profile = Profile(
        name="dev",
        access_token="sample-access",  # nosec B106 - synthetic token for tests
        refresh_token="sample-refresh",  # nosec B106 - synthetic token for tests
    )
    cfg = ConfigData(default_profile="dev", profiles={"dev": profile})
    store.save(cfg)

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    stored_profile = raw["profiles"]["dev"]
    assert stored_profile["access_token"].startswith("enc:")
    assert stored_profile["refresh_token"].startswith("enc:")

    loaded = store.load()
    assert loaded.profiles["dev"].access_token == "sample-access"  # nosec B105
    assert loaded.profiles["dev"].refresh_token == "sample-refresh"  # nosec B105
