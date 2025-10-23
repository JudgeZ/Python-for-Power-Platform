from __future__ import annotations

import os

import typer

from .config import ConfigData, ConfigStore


def _ensure_config(config: ConfigData | None) -> ConfigData:
    return config or ConfigStore().load()


def resolve_environment_id(option_value: str | None, *, config: ConfigData | None = None) -> str:
    """Return the effective environment id for a CLI command."""

    if option_value:
        return option_value

    cfg = _ensure_config(config)
    if cfg.environment_id:
        return cfg.environment_id

    raise typer.BadParameter(
        "Environment ID is not configured. Pass --environment-id or run "
        "`ppx profile set-env --environment-id <id>` to persist a default."
    )


def resolve_dataverse_host(option_value: str | None, *, config: ConfigData | None = None) -> str:
    """Return the Dataverse host for commands that require it."""

    if option_value:
        return option_value

    env_host = os.getenv("DATAVERSE_HOST")
    if env_host:
        return env_host

    cfg = _ensure_config(config)
    if cfg.dataverse_host:
        return cfg.dataverse_host

    raise typer.BadParameter(
        "Dataverse host is not configured. Pass --host, export DATAVERSE_HOST, or run "
        "`ppx profile set-host --host <org.crm.dynamics.com>`."
    )
