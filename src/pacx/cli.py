from __future__ import annotations

from pathlib import Path

from .cli import (
    app,
    auth,
    connectors,
    dataverse,
    doctor,
    pages,
    power_platform,
    profile,
    pva,
)

PACKAGE_DIR = Path(__file__).with_name("cli")
if PACKAGE_DIR.exists():
    __path__ = [str(PACKAGE_DIR)]


__all__ = [
    "app",
    "auth",
    "connectors",
    "dataverse",
    "doctor",
    "pages",
    "power_platform",
    "profile",
    "pva",
]
