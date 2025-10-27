from __future__ import annotations

from pathlib import Path

from .cli import (
    app,
    app_management,
    auth,
    connectors,
    dataverse,
    doctor,
    policy,
    governance,
    licensing,
    pages,
    power_platform,
    profile,
    tenant,
    pva,
    users,
)

PACKAGE_DIR = Path(__file__).with_name("cli")
if PACKAGE_DIR.exists():
    __path__ = [str(PACKAGE_DIR)]


__all__ = [
    "app",
    "app_management",
    "auth",
    "connectors",
    "dataverse",
    "doctor",
    "policy",
    "governance",
    "licensing",
    "pages",
    "power_platform",
    "profile",
    "tenant",
    "pva",
    "users",
]
