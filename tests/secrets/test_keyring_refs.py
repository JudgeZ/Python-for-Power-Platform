from __future__ import annotations

import pytest

from pacx.secrets import (
    SecretSpec,
    build_refresh_token_keyring_ref,
    delete_keyring_secret,
    get_secret,
    store_keyring_secret,
)


class StubKeyring:
    def __init__(self) -> None:
        self.storage: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.storage.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.storage[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.storage.pop((service_name, username), None)


def test_store_and_fetch_keyring_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubKeyring()
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: stub)

    ref = build_refresh_token_keyring_ref("example")
    success, reason = store_keyring_secret(ref, "secret-value")
    assert success is True
    assert reason is None

    stored = get_secret(SecretSpec(backend="keyring", ref=ref))
    assert stored == "secret-value"

    deleted, delete_reason = delete_keyring_secret(ref)
    assert deleted is True
    assert delete_reason is None
    assert stub.storage == {}


def test_keyring_secret_fallback_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: None)

    ref = build_refresh_token_keyring_ref("missing")
    success, reason = store_keyring_secret(ref, "value")
    assert success is False
    assert reason == "module-unavailable"

    deleted, delete_reason = delete_keyring_secret(ref)
    assert deleted is False
    assert delete_reason == "module-unavailable"
