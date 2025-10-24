from __future__ import annotations

"""Commands for inspecting and mutating stored PACX profiles."""

import typer
from rich import print

from ..config import ConfigStore
from .common import handle_cli_errors

app = typer.Typer(help="Profiles & configuration")


@app.command("list")
@handle_cli_errors
def profile_list() -> None:
    """Show all saved profiles, highlighting the default profile."""

    store = ConfigStore()
    cfg = store.load()
    names = sorted(list(cfg.profiles.keys())) if cfg.profiles else []
    for name in names:
        star = "*" if cfg.default_profile == name else " "
        print(f"{star} {name}")


@app.command("show")
@handle_cli_errors
def profile_show(name: str = typer.Argument(..., help="Profile name")) -> None:
    """Display the stored configuration for a profile."""

    store = ConfigStore()
    cfg = store.load()
    profile = cfg.profiles.get(name) if cfg.profiles else None
    if not profile:
        raise typer.BadParameter(f"Profile '{name}' not found")
    print(profile.__dict__)


@app.command("set-env")
@handle_cli_errors
def profile_set_env(
    environment_id: str = typer.Argument(..., help="Default Environment ID")
) -> None:
    """Persist a default environment ID for subsequent CLI commands."""

    store = ConfigStore()
    cfg = store.load()
    cfg.environment_id = environment_id
    store.save(cfg)
    print(f"Default environment set to {environment_id}")


@app.command("set-host")
@handle_cli_errors
def profile_set_host(
    dataverse_host: str = typer.Argument(..., help="Default Dataverse host")
) -> None:
    """Persist a default Dataverse host URL for CLI commands."""

    store = ConfigStore()
    cfg = store.load()
    cfg.dataverse_host = dataverse_host
    store.save(cfg)
    print(f"Default Dataverse host set to {dataverse_host}")


__all__ = [
    "app",
    "profile_list",
    "profile_show",
    "profile_set_env",
    "profile_set_host",
]
