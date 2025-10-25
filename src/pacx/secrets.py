from __future__ import annotations

from importlib import import_module
from typing import Any, Protocol, cast

from dataclasses import dataclass


class KeyringModule(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None:
        ...


class KeyVaultSecret(Protocol):
    value: str | None


class SecretClientProtocol(Protocol):
    def __init__(self, *, vault_url: str, credential: object) -> None:
        ...

    def get_secret(self, name: str) -> KeyVaultSecret:
        ...


class DefaultAzureCredentialFactory(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> object:
        ...


def _load_keyring() -> KeyringModule | None:
    try:
        module = import_module("keyring")
    except Exception:
        return None
    return cast(KeyringModule, module)


def _load_keyvault() -> tuple[DefaultAzureCredentialFactory, type[SecretClientProtocol]] | None:
    try:
        identity_module = import_module("azure.identity")
        secrets_module = import_module("azure.keyvault.secrets")
    except Exception:
        return None

    credential_factory = getattr(identity_module, "DefaultAzureCredential", None)
    secret_client_cls = getattr(secrets_module, "SecretClient", None)
    if credential_factory is None or secret_client_cls is None:
        return None

    return cast(DefaultAzureCredentialFactory, credential_factory), cast(
        type[SecretClientProtocol], secret_client_cls
    )


@dataclass
class SecretSpec:
    backend: str  # "env", "keyring", "keyvault"
    ref: str  # env: VAR, keyring: SERVICE:USERNAME, keyvault: VAULT_URL:SECRET_NAME


def get_secret(spec: SecretSpec) -> str | None:
    backend = spec.backend.lower()
    if backend == "env":
        import os

        return os.getenv(spec.ref)
    if backend == "keyring":
        keyring_module = _load_keyring()
        if keyring_module is None:
            return None
        try:
            service, username = spec.ref.split(":", 1)
        except ValueError:
            return None
        return keyring_module.get_password(service, username)
    if backend == "keyvault":
        resolved = _load_keyvault()
        if resolved is None:
            return None
        credential_factory, secret_client_cls = resolved
        try:
            # The vault URL itself may contain colon characters (e.g. the
            # ``https://`` scheme or custom ports). Split from the right so the
            # final segment is always treated as the secret name.
            vault_url, secret_name = spec.ref.rsplit(":", 1)
        except ValueError:
            return None
        credential = credential_factory()
        client = secret_client_cls(vault_url=vault_url, credential=credential)
        return client.get_secret(secret_name).value
    return None
