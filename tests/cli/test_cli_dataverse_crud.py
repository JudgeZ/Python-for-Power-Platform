from __future__ import annotations

import json

import httpx
import pytest
from typer.testing import CliRunner

from pacx.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")


def test_cli_dv_get(respx_mock) -> None:
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/accounts(00000000-0000-0000-0000-000000000000)"
    ).mock(
        return_value=httpx.Response(200, json={"accountid": "00000000-0000-0000-0000-000000000000"})
    )
    result = runner.invoke(app, ["dv", "get", "accounts", "00000000-0000-0000-0000-000000000000"])
    assert result.exit_code == 0
    assert "accountid" in result.output


def test_cli_dv_create(respx_mock) -> None:
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/accounts").mock(
        return_value=httpx.Response(
            201,
            headers={
                "OData-EntityId": "https://example.crm.dynamics.com/api/data/v9.2/accounts(42)"
            },
            json={"name": "Contoso"},
        )
    )
    payload = json.dumps({"name": "Contoso"})
    result = runner.invoke(app, ["dv", "create", "accounts", "--data", payload])
    assert result.exit_code == 0
    assert "Contoso" in result.output


def test_cli_dv_update(respx_mock) -> None:
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/accounts(42)").mock(
        return_value=httpx.Response(204)
    )
    result = runner.invoke(app, ["dv", "update", "accounts", "42", "--data", '{"name":"New"}'])
    assert result.exit_code == 0
    assert "updated" in result.output


def test_cli_dv_delete(respx_mock) -> None:
    respx_mock.delete("https://example.crm.dynamics.com/api/data/v9.2/accounts(42)").mock(
        return_value=httpx.Response(204)
    )
    result = runner.invoke(app, ["dv", "delete", "accounts", "42"])
    assert result.exit_code == 0
    assert "deleted" in result.output


def test_cli_dv_query(respx_mock) -> None:
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/accounts").mock(
        return_value=httpx.Response(200, json={"value": [{"name": "A"}]})
    )
    result = runner.invoke(app, ["dv", "query", "accounts", "--top", "1"])
    assert result.exit_code == 0
    assert "A" in result.output


def test_cli_dv_get_404(respx_mock) -> None:
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/accounts(999)").mock(
        return_value=httpx.Response(404, text="not found")
    )
    result = runner.invoke(app, ["dv", "get", "accounts", "999"])
    assert result.exit_code != 0
    assert "HTTP 404" in result.output
