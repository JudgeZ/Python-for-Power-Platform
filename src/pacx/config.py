from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import stat
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

LOGGER = logging.getLogger(__name__)

def _pacx_dir() -> Path:
    return Path(os.path.expanduser(os.getenv("PACX_HOME", "~/.pacx")))


def _config_path() -> Path:
    return _pacx_dir() / "config.json"


PACX_DIR = str(_pacx_dir())
CONFIG_PATH = str(_config_path())

_SENSITIVE_PROFILE_FIELDS = frozenset({"access_token"})
_ENCRYPTION_MARKER = "__pacx_encrypted__"


class ConfigEncryptionError(RuntimeError):
    """Raised when encrypted configuration values cannot be decrypted."""


def _empty_config() -> dict[str, Any]:
    return {
        "default": None,
        "profiles": {},
        "environment_id": None,
        "dataverse_host": None,
    }


def _ensure_dir() -> None:
    _pacx_dir().mkdir(parents=True, exist_ok=True)


def _ensure_secure_permissions(path: Path) -> None:
    """Apply restrictive (0600) permissions to ``path`` when possible."""

    try:
        desired_mode = stat.S_IRUSR | stat.S_IWUSR
        if os.name == "posix":
            current = stat.S_IMODE(path.stat().st_mode)
            if current & (stat.S_IRWXG | stat.S_IRWXO):
                LOGGER.warning(
                    "Relaxed permissions detected for %s (%o); tightening to 0600.",
                    path,
                    current,
                )
                os.chmod(path, desired_mode)
            elif current != desired_mode:
                os.chmod(path, desired_mode)
        else:
            os.chmod(path, desired_mode)
    except FileNotFoundError:
        return
    except OSError as exc:  # pragma: no cover - platform specific
        LOGGER.warning("Could not enforce secure permissions on %s: %s", path, exc)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_config()
    _ensure_secure_permissions(path)
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return _decrypt_config(raw, _get_fernet())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialised = _encrypt_config(payload, _get_fernet())
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(serialised, handle, indent=2)
    tmp.replace(path)
    _ensure_secure_permissions(path)


def _encrypt_config(data: dict[str, Any], fernet: Any | None) -> dict[str, Any]:
    if not fernet:
        return deepcopy(data)

    encoded = deepcopy(data)
    profiles = encoded.get("profiles")
    if isinstance(profiles, dict):
        for name, details in profiles.items():
            if isinstance(details, dict):
                profiles[name] = _encrypt_profile(details, fernet)
    return encoded


def _decrypt_config(raw: dict[str, Any], fernet: Any | None) -> dict[str, Any]:
    cfg = deepcopy(raw)
    profiles: dict[str, Any] = {}
    raw_profiles = cfg.get("profiles")
    if isinstance(raw_profiles, dict):
        for name, details in raw_profiles.items():
            if isinstance(details, dict):
                profiles[name] = _decrypt_profile(details, fernet)
    cfg["profiles"] = profiles
    cfg.setdefault("default", None)
    cfg.setdefault("environment_id", None)
    cfg.setdefault("dataverse_host", None)
    return cfg


def _encrypt_profile(profile: dict[str, Any], fernet: Any) -> dict[str, Any]:
    encrypted = dict(profile)
    for field_name in _SENSITIVE_PROFILE_FIELDS:
        if field_name in encrypted:
            encrypted[field_name] = _encrypt_sensitive_value(encrypted[field_name], fernet)
    return encrypted


def _decrypt_profile(profile: dict[str, Any], fernet: Any | None) -> dict[str, Any]:
    decrypted = dict(profile)
    for field_name in _SENSITIVE_PROFILE_FIELDS:
        if field_name in decrypted:
            decrypted[field_name] = _decrypt_sensitive_value(decrypted[field_name], fernet)
    return decrypted


def _encrypt_sensitive_value(value: Any, fernet: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return {_ENCRYPTION_MARKER: True, "value": token}


def _decrypt_sensitive_value(value: Any, fernet: Any | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict) and value.get(_ENCRYPTION_MARKER):
        if not fernet:
            raise ConfigEncryptionError(
                "Encrypted PACX config detected but PACX_CONFIG_ENCRYPTION_KEY is not set."
            )
        token = value.get("value")
        if not isinstance(token, str):
            raise ConfigEncryptionError("Encrypted PACX config is malformed.")
        try:
            decrypted_bytes = cast(bytes, fernet.decrypt(token.encode("utf-8")))
            decrypted = decrypted_bytes.decode("utf-8")
        except Exception as exc:  # pragma: no cover - indicates tampering
            raise ConfigEncryptionError(
                "Failed to decrypt PACX config. Double-check PACX_CONFIG_ENCRYPTION_KEY."
            ) from exc
        return decrypted
    if isinstance(value, str):
        return value
    return None


@lru_cache(maxsize=1)
def _get_fernet() -> Any | None:
    key = os.getenv("PACX_CONFIG_ENCRYPTION_KEY")
    if not key:
        LOGGER.debug("PACX_CONFIG_ENCRYPTION_KEY not set; storing config in plaintext.")
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError:  # pragma: no cover - optional dependency not installed
        LOGGER.warning(
            "PACX_CONFIG_ENCRYPTION_KEY is set but the 'cryptography' package is not installed. "
            "Configuration will be stored unencrypted."
        )
        return None
    derived = _derive_fernet_key(key)
    return Fernet(derived)


def _derive_fernet_key(raw_key: str) -> bytes:
    candidate = raw_key.encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(candidate)
        if len(decoded) == 32:
            return candidate
    except (binascii.Error, ValueError):
        pass
    digest = hashlib.sha256(candidate).digest()
    return base64.urlsafe_b64encode(digest)


def _clear_cached_encryption() -> None:
    """Reset cached encryption state (intended for tests)."""

    _get_fernet.cache_clear()


@dataclass
class Profile:
    name: str
    tenant_id: str | None = None
    client_id: str | None = None
    scope: str | None = None
    dataverse_host: str | None = None
    environment_id: str | None = None
    access_token: str | None = None
    client_secret_env: str | None = None
    secret_backend: str | None = None
    secret_ref: str | None = None
    scopes: list[str] | None = None


def load_config() -> dict[str, Any]:
    _ensure_dir()
    return _load_json(_config_path())


def save_config(cfg: dict[str, Any]) -> None:
    _ensure_dir()
    _write_json(_config_path(), cfg)


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
    return cast(str | None, prof.get("access_token"))


@dataclass
class ConfigData:
    default_profile: str | None = None
    profiles: dict[str, Profile] = field(default_factory=dict)
    environment_id: str | None = None
    dataverse_host: str | None = None


class ConfigStore:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path else _config_path()

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        self._ensure()
        return _load_json(self.path)

    def _write(self, data: dict[str, Any]) -> None:
        self._ensure()
        _write_json(self.path, data)

    def load(self) -> ConfigData:
        raw = self._read()
        profs = {
            name: Profile(name=name, **{k: v for k, v in data.items() if k != "name"})
            for name, data in raw.get("profiles", {}).items()
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
            "profiles": {name: asdict(profile) for name, profile in cfg.profiles.items()},
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
