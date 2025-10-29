from __future__ import annotations

import pytest

from pacx.secrets import SecretSpec, get_secret, set_secret


class StubKeyring:
    def __init__(self) -> None:
        self.storage: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, username: str) -> str | None:
        return self.storage.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        self.storage[(service_name, username)] = password


def test_set_secret_keyring_success(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubKeyring()
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: stub)

    spec = SecretSpec(backend="keyring", ref="svc:user")
    ok, reason = set_secret(spec, "secret-value")

    assert ok is True and reason is None
    # Verify round-trip via getter
    assert get_secret(spec) == "secret-value"


def test_set_secret_keyring_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: None)
    ok, reason = set_secret(SecretSpec(backend="keyring", ref="svc:user"), "value")
    assert ok is False and reason == "module-unavailable"


def test_set_secret_unsupported_backend() -> None:
    ok, reason = set_secret(SecretSpec(backend="env", ref="ENV_VAR"), "value")
    assert ok is False and reason == "unsupported-backend"


def test_set_secret_keyring_invalid_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keyring present with a setter, but ref is malformed (no ':')
    class KR:
        def set_password(self, *_: str) -> None:  # noqa: D401 - simple stub
            pass

    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: KR())
    ok, reason = set_secret(SecretSpec(backend="keyring", ref="invalid"), "value")
    assert ok is False and reason == "invalid-ref"
