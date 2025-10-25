from __future__ import annotations

import json
from pathlib import Path

import pytest

import pacx.config as config_module
from pacx.config import ConfigStore, get_profile


def _prepare_legacy_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(config_path), raising=False)

    legacy_profile = {
        "name": "legacy",
        "tenant_id": "tid",
        "client_id": "cid",
        # provider omitted to simulate older config versions
    }
    config_path.write_text(
        json.dumps({"default": "legacy", "profiles": {"legacy": legacy_profile}}),
        encoding="utf-8",
    )
    return config_path


def test_config_store_defaults_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = _prepare_legacy_config(tmp_path, monkeypatch)
    store = ConfigStore(path=config_path)

    cfg = store.load()
    assert cfg.profiles["legacy"].provider == "azure"


def test_get_profile_defaults_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_legacy_config(tmp_path, monkeypatch)
    profile = get_profile("legacy")
    assert profile is not None
    assert profile.provider == "azure"
