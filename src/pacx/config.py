from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

PACX_DIR = os.path.expanduser(os.getenv("PACX_HOME", "~/.pacx"))
CONFIG_PATH = os.path.join(PACX_DIR, "config.json")

__all__ = ["ConfigStore", "Profile"]


@dataclass
class Profile:
    """Represents an authentication profile stored in the PACX config file."""

    name: str
    tenant_id: str | None = None
    client_id: str | None = None
    dataverse_host: str | None = None
    scope: str | None = None
    scopes: list[str] | None = None
    access_token: str | None = None
    client_secret_env: str | None = None
    secret_backend: str | None = None
    secret_ref: str | None = None
    extras: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Profile":
        payload: Dict[str, Any] = dict(data or {})
        payload.setdefault("name", name)

        known_keys = {
            "name",
            "tenant_id",
            "client_id",
            "dataverse_host",
            "scope",
            "scopes",
            "access_token",
            "client_secret_env",
            "secret_backend",
            "secret_ref",
        }
        extras = {k: v for k, v in payload.items() if k not in known_keys}
        profile_data = {k: payload.get(k) for k in known_keys if k in payload}

        scopes_value = profile_data.get("scopes")
        if profile_data.get("scope") is None and isinstance(scopes_value, list) and scopes_value:
            profile_data["scope"] = scopes_value[0]
        elif "scopes" not in profile_data and profile_data.get("scope"):
            profile_data["scopes"] = [profile_data["scope"]]

        profile_data["extras"] = extras
        return cls(**profile_data)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        extras = data.pop("extras", {})
        if data.get("scope") and not data.get("scopes"):
            data["scopes"] = [data["scope"]]
        scopes_value = data.get("scopes")
        if not data.get("scope") and isinstance(scopes_value, list) and scopes_value:
            data["scope"] = scopes_value[0]
        data = {k: v for k, v in data.items() if v is not None}
        data.update(extras)
        return data


@dataclass
class ConfigData:
    default_profile: str | None = None
    environment_id: str | None = None
    dataverse_host: str | None = None
    profiles: Dict[str, Profile] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ConfigData":
        payload: Dict[str, Any] = dict(raw or {})
        profiles_raw = payload.pop("profiles", {}) or {}
        default_profile = payload.pop("default", None)
        environment_id = payload.pop("environment_id", None)
        dataverse_host = payload.pop("dataverse_host", None)
        extras = payload

        profiles: Dict[str, Profile] = {}
        for name, data in profiles_raw.items():
            if not isinstance(data, dict):
                continue
            try:
                profiles[name] = Profile.from_dict(name, data)
            except TypeError:
                # Skip malformed entries but keep raw value in extras for preservation
                extras.setdefault("profiles_raw", {})[name] = data

        return cls(
            default_profile=default_profile,
            environment_id=environment_id,
            dataverse_host=dataverse_host,
            profiles=profiles,
            extras=extras,
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = dict(self.extras)
        if self.default_profile is not None:
            data["default"] = self.default_profile
        if self.environment_id is not None:
            data["environment_id"] = self.environment_id
        if self.dataverse_host is not None:
            data["dataverse_host"] = self.dataverse_host
        data["profiles"] = {name: profile.to_dict() for name, profile in self.profiles.items()}
        return data


class ConfigStore:
    """Persist PACX configuration to a JSON file on disk."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = os.path.expanduser(config_path or CONFIG_PATH)

    @property
    def config_path(self) -> str:
        return self._config_path

    def _ensure_dir(self) -> None:
        directory = os.path.dirname(self._config_path) or "."
        os.makedirs(directory, exist_ok=True)

    def load(self) -> ConfigData:
        self._ensure_dir()
        if not os.path.exists(self._config_path):
            return ConfigData()
        with open(self._config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return ConfigData.from_dict(raw)

    def save(self, config: ConfigData) -> ConfigData:
        self._ensure_dir()
        tmp_path = self._config_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)
        os.replace(tmp_path, self._config_path)
        return config

    def list_profiles(self) -> list[str]:
        cfg = self.load()
        return sorted(cfg.profiles.keys())

    def get_profile(self, name: str) -> Optional[Profile]:
        cfg = self.load()
        return cfg.profiles.get(name)

    def add_or_update_profile(self, profile: Profile, set_default: bool = False) -> ConfigData:
        cfg = self.load()
        cfg.profiles[profile.name] = profile
        if set_default or not cfg.default_profile:
            cfg.default_profile = profile.name
        return self.save(cfg)

    def delete_profile(self, name: str) -> ConfigData:
        cfg = self.load()
        if name in cfg.profiles:
            del cfg.profiles[name]
        if cfg.default_profile == name:
            cfg.default_profile = None
        return self.save(cfg)

    def set_default_profile(self, name: str) -> ConfigData:
        cfg = self.load()
        if name not in cfg.profiles:
            raise KeyError(f"Profile '{name}' not found")
        cfg.default_profile = name
        return self.save(cfg)

    def get_default_profile_name(self) -> Optional[str]:
        cfg = self.load()
        return cfg.default_profile

    def get_token_for_profile(self, name: Optional[str]) -> Optional[str]:
        cfg = self.load()
        target = name or cfg.default_profile
        if not target:
            return None
        prof = cfg.profiles.get(target)
        if not prof:
            return None
        return prof.access_token


# Backwards compatible helper functions

def load_config() -> Dict[str, Any]:
    return ConfigStore().load().to_dict()


def save_config(cfg: Dict[str, Any]) -> None:
    store = ConfigStore()
    data = ConfigData.from_dict(cfg)
    store.save(data)


def list_profiles() -> list[str]:
    return ConfigStore().list_profiles()


def get_default_profile_name() -> Optional[str]:
    return ConfigStore().get_default_profile_name()


def set_default_profile(name: str) -> None:
    ConfigStore().set_default_profile(name)


def get_profile(name: str) -> Optional[Profile]:
    return ConfigStore().get_profile(name)


def upsert_profile(p: Profile, set_default: bool = False) -> None:
    ConfigStore().add_or_update_profile(p, set_default=set_default)


def delete_profile(name: str) -> None:
    ConfigStore().delete_profile(name)


def get_token_for_profile(name: Optional[str]) -> Optional[str]:
    return ConfigStore().get_token_for_profile(name)
