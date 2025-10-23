from __future__ import annotations

from pathlib import Path

import typer

from .cli import auth, connectors, dataverse, doctor, pages, power_platform, profile

PACKAGE_DIR = Path(__file__).with_name("cli")
if PACKAGE_DIR.exists():
    __path__ = [str(PACKAGE_DIR)]

app = typer.Typer(help="PACX CLI")
app.add_typer(auth.app, name="auth")
app.add_typer(profile.app, name="profile")
app.add_typer(dataverse.app, name="dv")
app.add_typer(connectors.app, name="connector")
app.add_typer(pages.app, name="pages")

doctor.register(app)
power_platform.register(app)


@app.callback()
def common(ctx: typer.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj.setdefault("token_getter", None)


__all__ = [
    "app",
    "auth",
    "connectors",
    "dataverse",
    "doctor",
    "pages",
    "power_platform",
    "profile",
]
