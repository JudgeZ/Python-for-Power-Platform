"""Shared helpers for repository automation scripts."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from enum import IntEnum
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings as _BaseSettings
else:  # pragma: no cover
    try:
        from pydantic_settings import BaseSettings as _BaseSettings
    except ModuleNotFoundError:
        _BaseSettings = BaseModel


LOG_LEVEL_ENV: Final[str] = "LOG_LEVEL"


class ExitCode(IntEnum):
    """Common exit codes for automation scripts."""

    SUCCESS = 0
    FAILURE = 1
    MISSING_DEPENDENCY = 2

    def exit(self) -> None:
        raise SystemExit(int(self))


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with level sourced from ``LOG_LEVEL``."""

    level_name = os.getenv(LOG_LEVEL_ENV, "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s - %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


class Settings(_BaseSettings):
    """Runtime settings exposed via environment variables."""

    spectral_cmd: str = Field(
        default="npx -y @stoplight/spectral lint",
        description="Command used to invoke Spectral",
    )
    openapi_glob: str = Field(
        default="openapi/*.yaml,openapi/*.yml",
        description="Glob used to discover OpenAPI specifications",
    )
    concurrency: int = Field(
        default_factory=lambda: os.cpu_count() or 1,
        description="Maximum number of worker threads",
    )
    report_json: str | None = Field(
        default=None,
        description="Optional JSON report output path",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "PACX_",
    }


def run_command(
    cmd: Iterable[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
) -> CompletedProcess[str]:
    """Execute ``cmd`` returning a completed process with captured output."""

    return run(  # noqa: S603
        list(cmd),
        cwd=str(cwd) if cwd else None,
        check=check,
        capture_output=True,
        text=True,
    )


def exit_success() -> None:
    """Exit the script indicating success."""

    ExitCode.SUCCESS.exit()


def exit_failure(message: str | None = None) -> None:
    """Exit the script with failure, optionally logging ``message``."""

    if message:
        logging.getLogger(__name__).error("%s", message)
    ExitCode.FAILURE.exit()


def exit_missing_dependency(message: str) -> None:
    """Exit with a consistent missing-dependency error code."""

    logging.getLogger(__name__).error("%s", message)
    ExitCode.MISSING_DEPENDENCY.exit()
