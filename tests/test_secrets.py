from __future__ import annotations

from dataclasses import dataclass

import pytest

from pacx.secrets import SecretSpec, get_secret


def test_get_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV_TOKEN", "super-secret")
    spec = SecretSpec(backend="env", ref="ENV_TOKEN")
    assert get_secret(spec) == "super-secret"


def test_get_secret_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubKeyring:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def get_password(self, service_name: str, username: str) -> str | None:
            self.calls.append((service_name, username))
            return "keyring-secret"

    stub = StubKeyring()
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: stub)
    spec = SecretSpec(backend="keyring", ref="svc:user")
    assert get_secret(spec) == "keyring-secret"
    assert stub.calls == [("svc", "user")]


def test_get_secret_keyring_invalid_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pacx.secrets._load_keyring", lambda: object())
    spec = SecretSpec(backend="keyring", ref="missing-delimiter")
    assert get_secret(spec) is None


@dataclass
class StubSecret:
    value: str | None


class StubSecretClient:
    def __init__(self, *, vault_url: str, credential: object) -> None:
        self.vault_url = vault_url
        self.credential = credential
        self.requests: list[str] = []

    def get_secret(self, name: str) -> StubSecret:
        self.requests.append(name)
        return StubSecret("vault-secret")


def test_get_secret_keyvault(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pacx.secrets._load_keyvault",
        lambda: (lambda: object(), StubSecretClient),
    )
    spec = SecretSpec(backend="keyvault", ref="https://vault:secret-name")
    assert get_secret(spec) == "vault-secret"


def test_get_secret_keyvault_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pacx.secrets._load_keyvault", lambda: None)
    spec = SecretSpec(backend="keyvault", ref="vault-only")
    assert get_secret(spec) is None


def test_get_secret_unknown_backend() -> None:
    spec = SecretSpec(backend="unknown", ref="value")
    assert get_secret(spec) is None
