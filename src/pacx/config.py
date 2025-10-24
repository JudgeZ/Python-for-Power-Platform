from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import stat
from importlib import import_module
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol, cast


class FernetProtocol(Protocol):
    def __init__(self, key: bytes) -> None:
        ...

    def encrypt(self, data: bytes) -> bytes:
        ...

    def decrypt(self, token: bytes, ttl: int | None = ...) -> bytes:
        ...


try:  # pragma: no cover - optional dependency
    _fernet_module: ModuleType | None = import_module("cryptography.fernet")
except Exception:  # pragma: no cover - library not available during runtime
    _fernet_module = None

if _fernet_module is not None:
    Fernet: type[FernetProtocol] | None = cast(
        "type[FernetProtocol]", getattr(_fernet_module, "Fernet")
    )
    InvalidToken = cast("type[Exception]", getattr(_fernet_module, "InvalidToken"))
else:
    Fernet = None

    class _FallbackInvalidToken(Exception):  # pragma: no cover - fallback when cryptography missing
        pass

    InvalidToken = _FallbackInvalidToken


logger = logging.getLogger(__name__)

PACX_DIR = os.path.expanduser(os.getenv("PACX_HOME", "~/.pacx"))
CONFIG_PATH = os.path.join(PACX_DIR, "config.json")

_SENSITIVE_KEYS = ("access_token",)
_FERNET_SALT = b"pacx-config"
_cached_cipher: FernetProtocol | None = None
_cached_cipher_key: str | None = None


class EncryptedConfigError(RuntimeError):
    """Raised when encrypted configuration cannot be decrypted."""


def _derive_fernet_key(raw: str) -> bytes | None:
    """Return a urlsafe base64 Fernet key derived from ``raw``."""

    if not raw:
        return None

    normalized = raw.strip().encode("utf-8")
    if not normalized:
        return None

    try:
        decoded = base64.urlsafe_b64decode(normalized)
    except (binascii.Error, ValueError):
        decoded = b""

    if len(decoded) == 32:
        return normalized

    derived = base64.urlsafe_b64encode(
        hashlib.pbkdf2_hmac("sha256", normalized, _FERNET_SALT, 390_000, dklen=32)
    )
    return derived


def _get_cipher() -> FernetProtocol | None:
    global _cached_cipher, _cached_cipher_key

    key = os.getenv("PACX_CONFIG_ENCRYPTION_KEY")
    if key != _cached_cipher_key:
        _cached_cipher = None
        _cached_cipher_key = key

    if not key:
        return None

    if Fernet is None:
        logger.info(
            "PACX_CONFIG_ENCRYPTION_KEY is set but cryptography is unavailable;"
            " storing config in plaintext."
        )
        return None

    if _cached_cipher is not None:
        return _cached_cipher

    derived = _derive_fernet_key(key)
    if not derived:
        logger.warning(
            "PACX_CONFIG_ENCRYPTION_KEY is invalid; expected a Fernet key or passphrase."
        )
        return None

    try:
        _cached_cipher = Fernet(derived)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unable to initialise Fernet cipher: %s", exc)
        _cached_cipher = None

    return _cached_cipher


def encrypt_field(value: str | None) -> str | None:
    """Encrypt ``value`` when an encryption key is configured."""

    if value is None or value == "":
        return value

    cipher = _get_cipher()
    if cipher is None:
        return value

    token = cipher.encrypt(value.encode("utf-8"))
    return f"enc:{token.decode('utf-8')}"


def decrypt_field(value: str | None) -> str | None:
    """Decrypt ``value`` produced by :func:`encrypt_field`."""

    if value is None or value == "":
        return value

    if not value.startswith("enc:"):
        return value

    cipher = _get_cipher()
    if cipher is None:
        raise EncryptedConfigError(
            "Encrypted PACX configuration detected but PACX_CONFIG_ENCRYPTION_KEY is not set."
        )

    token = value[4:].encode("utf-8")
    try:
        decrypted = cipher.decrypt(token)
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise RuntimeError("Unable to decrypt PACX configuration; verify encryption key.") from exc
    return decrypted.decode("utf-8")


def _secure_path(path: Path) -> None:
    if not path.exists():
        return

    try:
        if os.name == "nt":
            desired = stat.S_IREAD | stat.S_IWRITE
            os.chmod(path, desired)
        else:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                logger.warning("Adjusted permissions for %s to 0o600", path)
            path.chmod(0o600)
    except PermissionError as exc:
        logger.warning("Unable to enforce secure permissions for %s: %s", path, exc)


def _ensure_secure_permissions(path: Path) -> None:
    if not path.exists():
        return

    if os.name != "nt":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            logger.warning("Config file %s is world-accessible; resetting to 0o600.", path)
            _secure_path(path)
    else:
        _secure_path(path)


def _encrypt_profile_dict(profile: dict[str, Any]) -> dict[str, Any]:
    payload = dict(profile)
    for key in _SENSITIVE_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = encrypt_field(value)
    return payload


def _decrypt_profile_dict(profile: dict[str, Any]) -> dict[str, Any]:
    payload = dict(profile)
    for key in _SENSITIVE_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = decrypt_field(value)
    return payload


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


def _ensure_dir() -> None:
    os.makedirs(PACX_DIR, exist_ok=True)


def load_config() -> dict[str, Any]:
    _ensure_dir()
    path = Path(CONFIG_PATH)
    if not path.exists():
        return {"default": None, "profiles": {}}

    _ensure_secure_permissions(path)
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    raw["profiles"] = {
        name: _decrypt_profile_dict(profile) for name, profile in raw.get("profiles", {}).items()
    }
    return raw


def save_config(cfg: dict[str, Any]) -> None:
    _ensure_dir()
    path = Path(CONFIG_PATH)
    tmp = path.with_suffix(".tmp")

    payload = dict(cfg)
    payload["profiles"] = {
        name: _encrypt_profile_dict(profile)
        for name, profile in payload.get("profiles", {}).items()
    }

    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp.replace(path)
    _secure_path(path)


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
    return token if isinstance(token, str) else None


@dataclass
class ConfigData:
    default_profile: str | None = None
    profiles: dict[str, Profile] = field(default_factory=dict)
    environment_id: str | None = None
    dataverse_host: str | None = None


class ConfigStore:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path) if path else Path(CONFIG_PATH)

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        self._ensure()
        if not self.path.exists():
            return {"default": None, "profiles": {}}
        _ensure_secure_permissions(self.path)
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["profiles"] = {
            name: _decrypt_profile_dict(profile)
            for name, profile in raw.get("profiles", {}).items()
        }
        return raw

    def _write(self, data: dict[str, Any]) -> None:
        self._ensure()
        tmp = self.path.with_suffix(".tmp")
        payload = dict(data)
        payload["profiles"] = {
            name: _encrypt_profile_dict(
                asdict(profile) if isinstance(profile, Profile) else profile
            )
            for name, profile in payload.get("profiles", {}).items()
        }
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        tmp.replace(self.path)
        _secure_path(self.path)

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
            "profiles": cfg.profiles,
        }
        self._write(data)

    def add_or_update_profile(self, profile: Profile, *, set_default: bool = False) -> ConfigData:
        """Persist ``profile`` and optionally set it as default."""

        cfg = self.load()
        cfg.profiles[profile.name] = profile
        if set_default or not cfg.default_profile:
            cfg.default_profile = profile.name
        self.save(cfg)
        return cfg

    def set_default_profile(self, name: str) -> ConfigData:
        """Mark the profile ``name`` as the default profile."""

        cfg = self.load()
        if name not in cfg.profiles:
            raise KeyError(f"Profile '{name}' not found")
        cfg.default_profile = name
        self.save(cfg)
        return cfg
