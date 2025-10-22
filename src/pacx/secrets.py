
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SecretSpec:
    backend: str  # "env", "keyring", "keyvault"
    ref: str      # env: VAR, keyring: SERVICE:USERNAME, keyvault: VAULT_URL:SECRET_NAME


def get_secret(spec: SecretSpec) -> Optional[str]:
    backend = spec.backend.lower()
    if backend == "env":
        import os
        return os.getenv(spec.ref)
    if backend == "keyring":
        try:
            import keyring  # type: ignore
        except Exception:
            return None
        try:
            service, username = spec.ref.split(":", 1)
        except ValueError:
            return None
        return keyring.get_password(service, username)
    if backend == "keyvault":
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
        except Exception:
            return None
        try:
            vault_url, secret_name = spec.ref.split(":", 1)
        except ValueError:
            return None
        cred = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=cred)
        return client.get_secret(secret_name).value
    return None
