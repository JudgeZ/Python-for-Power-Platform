
from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from pacx.cli import app

runner = CliRunner()


def test_cli_dv_whoami(monkeypatch, respx_mock):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/WhoAmI()").mock(
        return_value=httpx.Response(200, json={"UserId": "000"})
    )
    result = runner.invoke(app, ["dv", "whoami"])
    assert result.exit_code == 0
    assert "UserId" in result.stdout
    assert respx_mock.calls[0].request.headers["Authorization"] == "Bearer dummy"


def test_cli_connector_push(monkeypatch, respx_mock, tmp_path):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    # Create a small openapi file
    p = tmp_path / "o.yaml"
    p.write_text("openapi: 3.0.3\ninfo:\n  title: t\n  version: 1\npaths: {}\n", encoding="utf-8")
    respx_mock.put(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"name": "myapi"}))
    result = runner.invoke(app, ["connector", "push", "--environment-id", "ENV", "--name", "myapi", "--openapi", str(p)])
    assert result.exit_code == 0
    assert "myapi" in result.stdout
