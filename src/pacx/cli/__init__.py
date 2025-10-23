from __future__ import annotations

import typer

from . import auth, connectors, dataverse, doctor, pages, power_platform, profile

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
    """Initialize shared Typer context state."""

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
