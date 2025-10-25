from __future__ import annotations

import sys
from pathlib import Path

import pytest
import respx
from typer.testing import CliRunner


# Ensure the repository-local ``src`` directory is importable when the project is
# not installed as a package. Pytest executes from the repository root where the
# ``src`` layout is not on ``sys.path`` by default, so the pacx package would
# otherwise be missing.
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@pytest.fixture
def token_getter():
    return lambda: "dummy-token"


@pytest.fixture
def respx_mock():
    with respx.mock(assert_all_called=False) as respx_mgr:
        yield respx_mgr


@pytest.fixture
def cli_runner(monkeypatch):
    """Provide a CLI runner with a dummy access token."""

    monkeypatch.setenv("PACX_ACCESS_TOKEN", "test-token")
    return CliRunner()
