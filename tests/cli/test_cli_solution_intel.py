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
    respx_mock: Any, solution_id: str = "00000000-0000-0000-0000-000000000001"
) -> str:
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/solutions").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "solutionid": solution_id,
                        "uniquename": "MySolution",
                        "friendlyname": "My Solution",
                    }
                ]
            },
        )
    )
    return solution_id


def test_solution_components_json(respx_mock: Any) -> None:
    sid = _mock_solution_lookup(respx_mock)
    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/solutions({sid})/solutioncomponents"
    ).mock(
        return_value=httpx.Response(200, json={"value": [{"componenttype": 61, "name": "comp"}]})
    )

    result = runner.invoke(app, ["solution", "components", "--name", "MySolution"])
    assert result.exit_code == 0, result.output
    assert "value" in result.output
    assert "componenttype" in result.output


def test_solution_deps_dot_format(respx_mock: Any) -> None:
    sid = _mock_solution_lookup(respx_mock)
    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/solutions({sid})/dependencies"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "dependentcomponentname": "A",
                        "requiredcomponentname": "B",
                    }
                ]
            },
        )
    )

    result = runner.invoke(app, ["solution", "deps", "--name", "MySolution", "--format", "dot"])
    assert result.exit_code == 0, result.output
    assert "digraph" in result.output and '"A" -> "B"' in result.output


def test_solution_check_ok(respx_mock: Any) -> None:
    sid = _mock_solution_lookup(respx_mock)
    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/solutions({sid})/dependencies"
    ).mock(return_value=httpx.Response(200, json={"value": []}))

    result = runner.invoke(app, ["solution", "check", "--name", "MySolution"])
    assert result.exit_code == 0, result.output
    assert "ok" in result.output and "True" in result.output
