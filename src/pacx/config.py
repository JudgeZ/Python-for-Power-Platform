from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any

PACX_DIR = os.path.expanduser(os.getenv("PACX_HOME", "~/.pacx"))
CONFIG_PATH = os.path.join(PACX_DIR, "config.json")

@dataclass
class Profile:
    name: str
    tenant_id: str | None = None
    client_id: str | None = None
    dataverse_host: str | None = None
    scopes: list[str] | None = None
    access_token: str | None = None

def _ensure_dir() -> None:
    os.makedirs(PACX_DIR, exist_ok=True)

def load_config() -> Dict[str, Any]:
    _ensure_dir()
    if not os.path.exists(CONFIG_PATH):
        return {"default": None, "profiles": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg: Dict[str, Any]) -> None:
    _ensure_dir()
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)

def list_profiles() -> list[str]:
    cfg = load_config()
    return sorted(cfg.get("profiles", {}).keys())

def get_default_profile_name() -> Optional[str]:
    cfg = load_config()
    return cfg.get("default")

def set_default_profile(name: str) -> None:
    cfg = load_config()
    if name not in cfg.get("profiles", {}):
        raise KeyError(f"Profile '{name}' not found")
    cfg["default"] = name
    save_config(cfg)

def get_profile(name: str) -> Optional[Profile]:
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

def get_token_for_profile(name: Optional[str]) -> Optional[str]:
    cfg = load_config()
    if not name:
        name = cfg.get("default")
    if not name:
        return None
    prof = cfg.get("profiles", {}).get(name, {})
    return prof.get("access_token")
