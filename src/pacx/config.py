from __future__ import annotations

import json
import logging
import os
import stat
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

try:  # pragma: no cover - optional dependency import path
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised in environments without crypto
    Fernet = None
    InvalidToken = Exception


logger = logging.getLogger(__name__)

PACX_DIR = os.path.expanduser(os.getenv("PACX_HOME", "~/.pacx"))
CONFIG_PATH = os.path.join(PACX_DIR, "config.json")


def _profile_to_mapping(profile: Profile) -> dict[str, Any]:
    data = asdict(profile)
    encrypted_value = data.pop("encrypted_access_token", None)
    token = data.get("access_token")

    if token is not None:
        data["access_token"] = token
    elif encrypted_value:
        data["access_token"] = {"encrypted": "fernet", "value": encrypted_value}
    else:
        data["access_token"] = None

    if encrypted_value:
        data["encrypted_access_token"] = encrypted_value
    return data


@dataclass
class Profile:
    name: str
    tenant_id: str | None = None
    client_id: str | None = None
    scope: str | None = None
    dataverse_host: str | None = None
    environment_id: str | None = None
    access_token: str | None = None
    encrypted_access_token: str | None = None
    client_secret_env: str | None = None
    secret_backend: str | None = None
    secret_ref: str | None = None
    scopes: list[str] | None = None


def _ensure_dir() -> None:
    os.makedirs(PACX_DIR, exist_ok=True)


def _ensure_secure_permissions(path: Path) -> None:
    """Restrict permissions on ``path`` to the current user only."""

    if not path.exists():
        return

    if sys.platform.startswith("win"):
        # ``os.chmod`` on Windows is limited but still clears group/other bits.
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as exc:  # pragma: no cover - platform dependent
            logger.debug("Unable to harden permissions for %s: %s", path, exc)
    else:
        try:
            current_mode = stat.S_IMODE(path.stat().st_mode)
            if current_mode != 0o600:
                os.chmod(path, 0o600)
                if current_mode & 0o077:
                    logger.warning(
                        "Adjusted permissions for %s to 0600 (previously %s)",
                        path,
                        oct(current_mode),
                    )
        except OSError as exc:  # pragma: no cover - filesystem edge cases
            logger.debug("Unable to adjust permissions for %s: %s", path, exc)


def _load_legacy_dict(store: ConfigStore) -> dict[str, Any]:
    cfg = store.load()
    return {
        "default": cfg.default_profile,
        "environment_id": cfg.environment_id,
        "dataverse_host": cfg.dataverse_host,
        "profiles": {name: _profile_to_mapping(profile) for name, profile in cfg.profiles.items()},
    }


def load_config() -> dict[str, Any]:
    store = ConfigStore()
    return _load_legacy_dict(store)


def _mapping_to_configdata(data: dict[str, Any]) -> ConfigData:
    profiles: dict[str, Profile] = {}
    raw_profiles = data.get("profiles", {}) or {}
    for name, payload in raw_profiles.items():
        if not isinstance(payload, dict):
            continue

        token_field = payload.get("access_token")
        encrypted_token = payload.get("encrypted_access_token")
        access_token: str | None = None

        if isinstance(token_field, dict) and token_field.get("encrypted") == "fernet":
            encrypted_token = token_field.get("value")
        elif isinstance(token_field, str):
            access_token = token_field

        profile = Profile(
            name=name,
            tenant_id=payload.get("tenant_id"),
            client_id=payload.get("client_id"),
            scope=payload.get("scope"),
            dataverse_host=payload.get("dataverse_host"),
            environment_id=payload.get("environment_id"),
            access_token=access_token,
            encrypted_access_token=encrypted_token,
            client_secret_env=payload.get("client_secret_env"),
            secret_backend=payload.get("secret_backend"),
            secret_ref=payload.get("secret_ref"),
            scopes=payload.get("scopes"),
        )
        profiles[name] = profile

    return ConfigData(
        default_profile=data.get("default"),
        profiles=profiles,
        environment_id=data.get("environment_id"),
        dataverse_host=data.get("dataverse_host"),
    )


def save_config(cfg: dict[str, Any]) -> None:
    store = ConfigStore()
    store.save(_mapping_to_configdata(cfg))


def list_profiles() -> list[str]:
    cfg = load_config()
    return sorted(cfg.get("profiles", {}).keys())


def get_default_profile_name() -> str | None:
    cfg = load_config()
    return cfg.get("default")


def set_default_profile(name: str) -> None:
    cfg = load_config()
    if name not in cfg.get("profiles", {}):
        raise KeyError(f"Profile '{name}' not found")
    cfg["default"] = name
    save_config(cfg)


def get_profile(name: str) -> Profile | None:
    cfg = load_config()
    data = cfg.get("profiles", {}).get(name)
    if not data:
        return None
    return Profile(**data)


def upsert_profile(p: Profile, set_default: bool = False) -> None:
    cfg = load_config()
    cfg.setdefault("profiles", {})
    cfg["profiles"][p.name] = asdict(p)
    if set_default or not cfg.get("default"):
        cfg["default"] = p.name
    save_config(cfg)


def delete_profile(name: str) -> None:
    cfg = load_config()
    if name in cfg.get("profiles", {}):
        del cfg["profiles"][name]
    if cfg.get("default") == name:
        cfg["default"] = None
    save_config(cfg)


def get_token_for_profile(name: str | None) -> str | None:
    cfg = load_config()
    if not name:
        name = cfg.get("default")
    if not name:
        return None
    prof = cfg.get("profiles", {}).get(name, {})
    token = prof.get("access_token")
    if isinstance(token, str):
        return token
    return None


@dataclass
class ConfigData:
    default_profile: str | None = None
    profiles: dict[str, Profile] = field(default_factory=dict)
    environment_id: str | None = None
    dataverse_host: str | None = None


class ConfigStore:
    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        encryption_key: str | bytes | None = None,
    ) -> None:
        self.path = Path(path) if path else Path(CONFIG_PATH)
        key = encryption_key or os.getenv("PACX_CONFIG_ENCRYPTION_KEY")
        self._fernet: Any | None = self._init_fernet(key)

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        self._ensure()
        if not self.path.exists():
            return {"default": None, "profiles": {}}
        _ensure_secure_permissions(self.path)
        with self.path.open("r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def _write(self, data: dict[str, Any]) -> None:
        self._ensure()
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(self.path)
        _ensure_secure_permissions(self.path)

    def _init_fernet(self, key: str | bytes | None) -> Any | None:
        if not key:
            return None
        if Fernet is None:
            logger.warning(
                "PACX_CONFIG_ENCRYPTION_KEY is set but cryptography is not installed; "
                "tokens will be stored in plaintext."
            )
            return None
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key
        try:
            return Fernet(key_bytes)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Invalid PACX_CONFIG_ENCRYPTION_KEY provided: %s. Tokens will be stored "
                "in plaintext.",
                exc,
            )
            return None

    def _encrypt(self, token: str) -> str | None:
        if not self._fernet:
            return None
        return cast(str, self._fernet.encrypt(token.encode("utf-8")).decode("utf-8"))

    def _decrypt(self, token: str) -> str | None:
        if not self._fernet:
            return None
        try:
            return cast(str, self._fernet.decrypt(token.encode("utf-8")).decode("utf-8"))
        except InvalidToken:
            logger.warning(
                "Failed to decrypt stored access token at %s; ignoring encrypted value.",
                self.path,
            )
            return None

    def _profile_from_payload(self, name: str, payload: dict[str, Any]) -> Profile:
        token_field = payload.get("access_token")
        encrypted_token: str | None = payload.get("encrypted_access_token")
        access_token: str | None = None

        if isinstance(token_field, dict) and token_field.get("encrypted") == "fernet":
            encrypted_token = token_field.get("value")
            if encrypted_token:
                decrypted = self._decrypt(encrypted_token)
                if decrypted:
                    access_token = decrypted
        elif isinstance(token_field, str):
            access_token = token_field

        profile = Profile(
            name=name,
            tenant_id=payload.get("tenant_id"),
            client_id=payload.get("client_id"),
            scope=payload.get("scope"),
            dataverse_host=payload.get("dataverse_host"),
            environment_id=payload.get("environment_id"),
            access_token=access_token,
            encrypted_access_token=encrypted_token,
            client_secret_env=payload.get("client_secret_env"),
            secret_backend=payload.get("secret_backend"),
            secret_ref=payload.get("secret_ref"),
            scopes=payload.get("scopes"),
        )
        return profile

    def _profile_to_payload(self, profile: Profile) -> dict[str, Any]:
        payload = asdict(profile)
        encrypted_value = payload.pop("encrypted_access_token", None)
        token = payload.get("access_token")

        stored_token: Any
        if token:
            encrypted_value = self._encrypt(token) or encrypted_value
            if encrypted_value:
                stored_token = {"encrypted": "fernet", "value": encrypted_value}
            else:
                stored_token = token
        elif encrypted_value:
            stored_token = {"encrypted": "fernet", "value": encrypted_value}
        else:
            stored_token = None

        if encrypted_value:
            profile.encrypted_access_token = encrypted_value
        if stored_token is None and "access_token" in payload:
            payload["access_token"] = None
        else:
            payload["access_token"] = stored_token
        return payload

    def load(self) -> ConfigData:
        raw = self._read()
        profs = {
            name: self._profile_from_payload(name, data)
            for name, data in raw.get("profiles", {}).items()
            if isinstance(data, dict)
        }
        return ConfigData(
            default_profile=raw.get("default"),
            profiles=profs,
            environment_id=raw.get("environment_id"),
            dataverse_host=raw.get("dataverse_host"),
        )

    def save(self, cfg: ConfigData) -> None:
        data = {
            "default": cfg.default_profile,
            "environment_id": cfg.environment_id,
            "dataverse_host": cfg.dataverse_host,
            "profiles": {
                name: self._profile_to_payload(profile) for name, profile in cfg.profiles.items()
            },
        }
        self._write(data)

    def add_or_update_profile(self, profile: Profile, *, set_default: bool = False) -> ConfigData:
        """Persist ``profile`` and optionally set it as default.

        Example:
            >>> store = ConfigStore("/tmp/pacx.json")
            >>> store.add_or_update_profile(Profile(name="dev"))

        Returns the updated :class:`ConfigData` snapshot for further mutation by
        callers (e.g. additional property edits before :meth:`save`).
        """

        cfg = self.load()
        cfg.profiles[profile.name] = profile
        if set_default or not cfg.default_profile:
            cfg.default_profile = profile.name
        self.save(cfg)
        return cfg

    def set_default_profile(self, name: str) -> ConfigData:
        """Mark the profile ``name`` as the default profile.

        Example:
            >>> store = ConfigStore("/tmp/pacx.json")
            >>> store.set_default_profile("dev")
        """

        cfg = self.load()
        if name not in cfg.profiles:
            raise KeyError(f"Profile '{name}' not found")
        cfg.default_profile = name
        self.save(cfg)
        return cfg
