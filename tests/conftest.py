from __future__ import annotations

import pytest
import respx
from typer.testing import CliRunner


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
