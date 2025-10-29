from __future__ import annotations

from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from pacx.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")


def _mock_solution_lookup(
    respx_mock: Any, sid: str = "00000000-0000-0000-0000-000000000042"
) -> str:
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/solutions").mock(
        return_value=httpx.Response(200, json={"value": [{"solutionid": sid, "uniquename": "Sol"}]})
    )
    return sid


def test_connection_list_json(respx_mock: Any) -> None:
    sid = _mock_solution_lookup(respx_mock)
    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/solutions({sid})/connectionreferences"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"connectionid": "c1", "connectorid": "cn1"},
                    {"connectionid": "", "connectorid": "cn2"},
                ]
            },
        )
    )
    out = runner.invoke(app, ["connection", "list", "--solution", "Sol"])
    assert out.exit_code == 0, out.output
    assert "value" in out.output


def test_connection_validate_flags_invalid(respx_mock: Any) -> None:
    sid = _mock_solution_lookup(respx_mock)
    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/solutions({sid})/connectionreferences"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"connectionid": "c1", "connectorid": "cn1"},
                    {"connectorid": "missing-connection"},
                ]
            },
        )
    )
    out = runner.invoke(app, ["connection", "validate", "--solution", "Sol"])
    assert out.exit_code != 0, out.output
    assert "invalid" in out.output
