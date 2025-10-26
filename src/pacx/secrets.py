from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

KEYRING_SERVICE_NAME = "pacx"
_KEYRING_REFRESH_PREFIX = "refresh-token"


class KeyringModule(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


class KeyVaultSecret(Protocol):
    value: str | None


class SecretClientProtocol(Protocol):
    def __init__(self, *, vault_url: str, credential: object) -> None: ...

    def get_secret(self, name: str) -> KeyVaultSecret: ...


class DefaultAzureCredentialFactory(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> object: ...


def _load_keyring() -> KeyringModule | None:
    try:
        module = import_module("keyring")
    except Exception:
        return None
    return cast(KeyringModule, module)


def build_refresh_token_keyring_ref(profile_name: str) -> str:
    """Return a deterministic keyring reference for ``profile_name`` refresh tokens."""

    return f"{KEYRING_SERVICE_NAME}:{_KEYRING_REFRESH_PREFIX}:{profile_name}"


def _split_keyring_ref(ref: str) -> tuple[str, str] | None:
    parts = ref.split(":", 1)
    if len(parts) != 2:
        return None
    service, username = parts
    if not service or not username:
        return None
    return service, username


def store_keyring_secret(ref: str, secret: str) -> tuple[bool, str | None]:
    """Persist ``secret`` to the system keyring referenced by ``ref``."""

    module = _load_keyring()
    if module is None:
        return False, "module-unavailable"
    setter = getattr(module, "set_password", None)
    if setter is None:
        return False, "setter-missing"
    parsed = _split_keyring_ref(ref)
    if parsed is None:
        return False, "invalid-ref"
    service, username = parsed
    try:
        setter(service, username, secret)
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, f"error:{exc.__class__.__name__}"
    return True, None


def delete_keyring_secret(ref: str) -> tuple[bool, str | None]:
    """Remove the password stored for ``ref`` from the system keyring."""

    module = _load_keyring()
    if module is None:
        return False, "module-unavailable"
    deleter = getattr(module, "delete_password", None)
    if deleter is None:
        return False, "deleter-missing"
    parsed = _split_keyring_ref(ref)
    if parsed is None:
        return False, "invalid-ref"
    service, username = parsed
    try:
        deleter(service, username)
    except Exception as exc:  # pragma: no cover - defensive guard
        return False, f"error:{exc.__class__.__name__}"
    return True, None


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
        parsed = _split_keyring_ref(spec.ref)
        if parsed is None:
            return None
        service, username = parsed
        getter = getattr(keyring_module, "get_password", None)
        if getter is None:
            return None
        typed_getter = cast(Callable[[str, str], str | None], getter)
        return typed_getter(service, username)
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
