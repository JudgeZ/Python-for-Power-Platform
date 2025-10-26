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
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: None)

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


def test_token_secret_fields_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    profile = Profile(
        name="with-token-secret",
        token_backend="keyring",  # noqa: S106
        token_ref="ppx-token",  # noqa: S106
    )
    cfg = ConfigData(default_profile="with-token-secret", profiles={"with-token-secret": profile})

    store.save(cfg)

    loaded = store.load()
    stored_profile = loaded.profiles["with-token-secret"]
    assert stored_profile.token_backend == "keyring"  # noqa: S105
    assert stored_profile.token_ref == "ppx-token"  # noqa: S105


def test_refresh_token_persisted_to_keyring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class StubKeyring:
        def __init__(self) -> None:
            self.storage: dict[tuple[str, str], str] = {}

        def get_password(self, service_name: str, username: str) -> str | None:
            return self.storage.get((service_name, username))

        def set_password(self, service_name: str, username: str, password: str) -> None:
            self.storage[(service_name, username)] = password

        def delete_password(self, service_name: str, username: str) -> None:
            self.storage.pop((service_name, username), None)

    stub = StubKeyring()
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: stub)

    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    profile = Profile(name="keyring-profile", refresh_token="r-token")  # noqa: S106
    cfg = ConfigData(default_profile="keyring-profile", profiles={"keyring-profile": profile})

    caplog.set_level("WARNING")
    store.save(cfg)

    raw = json.loads(path.read_text(encoding="utf-8"))
    stored_profile = raw["profiles"]["keyring-profile"]
    assert "refresh_token" not in stored_profile
    assert stored_profile["token_backend"] == "keyring"  # noqa: S105
    assert stored_profile["token_ref"] == "pacx:refresh-token:keyring-profile"  # noqa: S105
    assert stub.storage[("pacx", "refresh-token:keyring-profile")] == "r-token"
    assert not any("Keyring unavailable" in message for message in caplog.messages)

    loaded = store.load()
    keyring_profile = loaded.profiles["keyring-profile"]
    assert keyring_profile.refresh_token == "r-token"  # noqa: S105
    assert keyring_profile.token_backend == "keyring"  # noqa: S105
    assert keyring_profile.token_ref == "pacx:refresh-token:keyring-profile"  # noqa: S105


def test_refresh_token_fallback_logs_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: None)

    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    profile = Profile(name="no-keyring", refresh_token="fallback-token")  # noqa: S106
    cfg = ConfigData(default_profile="no-keyring", profiles={"no-keyring": profile})

    caplog.set_level("WARNING")
    store.save(cfg)

    raw = json.loads(path.read_text(encoding="utf-8"))
    stored_profile = raw["profiles"]["no-keyring"]
    assert stored_profile["refresh_token"] == "fallback-token"  # noqa: S105
    assert stored_profile.get("token_backend") is None
    assert stored_profile.get("token_ref") is None
    warning_records = [
        record for record in caplog.records if "Keyring unavailable" in record.getMessage()
    ]
    assert warning_records
    warning_record = warning_records[-1]
    assert warning_record.pacx_reason == "module-unavailable"
    assert warning_record.pacx_profile_hint == config_module._profile_log_hint("no-keyring")
    assert not hasattr(warning_record, "pacx_profile")


def test_refresh_token_fallback_redacts_dynamic_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing_store(ref: str, secret: str) -> tuple[bool, str | None]:  # noqa: ARG001
        return False, "error:RuntimeError"

    monkeypatch.setattr("pacx.config.store_keyring_secret", failing_store)

    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    profile = Profile(name="error-keyring", refresh_token="fallback-token")  # noqa: S106
    cfg = ConfigData(default_profile="error-keyring", profiles={"error-keyring": profile})

    caplog.set_level("WARNING")
    store.save(cfg)

    warning_record = next(
        record for record in caplog.records if "Keyring unavailable" in record.getMessage()
    )
    assert warning_record.pacx_reason == "error"
    assert warning_record.pacx_profile_hint == config_module._profile_log_hint("error-keyring")
    assert not hasattr(warning_record, "pacx_profile")


def test_delete_profile_removes_keyring_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubKeyring:
        def __init__(self) -> None:
            self.storage: dict[tuple[str, str], str] = {}

        def get_password(self, service_name: str, username: str) -> str | None:
            return self.storage.get((service_name, username))

        def set_password(self, service_name: str, username: str, password: str) -> None:
            self.storage[(service_name, username)] = password

        def delete_password(self, service_name: str, username: str) -> None:
            self.storage.pop((service_name, username), None)

    stub = StubKeyring()
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: stub)

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path))
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(config_path))

    cfg = {
        "default": "deleteme",
        "profiles": {
            "deleteme": {
                "name": "deleteme",
                "refresh_token": "to-be-removed",
            }
        },
    }

    config_module.save_config(cfg)
    assert stub.storage[("pacx", "refresh-token:deleteme")] == "to-be-removed"

    config_module.delete_profile("deleteme")

    assert ("pacx", "refresh-token:deleteme") not in stub.storage
