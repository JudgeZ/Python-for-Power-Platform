from __future__ import annotations

import httpx
from typer.testing import CliRunner

from pacx.bulk_csv import BulkCsvResult, BulkCsvStats
from pacx.cli import app, dataverse, power_platform

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
    assert respx_mock.calls, "expected Dataverse request"
    auth_header = respx_mock.calls.last.request.headers.get("Authorization")
    assert auth_header == "Bearer dummy"


def test_cli_dv_bulk_csv_exits_cleanly(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("accountid,name\n1,Example\n", encoding="utf-8")

    fake_result = BulkCsvResult(
        operations=[],
        stats=BulkCsvStats(
            total_rows=1,
            attempts=1,
            successes=1,
            failures=0,
            retry_invocations=0,
            retry_histogram={},
            grouped_errors={},
        ),
    )

    def fake_bulk_csv_upsert(*args, **kwargs):
        return fake_result

    monkeypatch.setattr(dataverse, "bulk_csv_upsert", fake_bulk_csv_upsert)

    result = runner.invoke(
        app,
        [
            "dv",
            "bulk-csv",
            "accounts",
            str(csv_path),
            "--id-column",
            "accountid",
        ],
    )

    assert result.exit_code == 0
    assert "Bulk upsert completed" in result.stdout
    assert result.stderr == ""


def test_cli_dv_bulk_csv_rejects_invalid_chunk_size(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    csv_path = tmp_path / "payload.csv"
    csv_path.write_text("accountid,name\n1,Example\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "dv",
            "bulk-csv",
            "accounts",
            str(csv_path),
            "--id-column",
            "accountid",
            "--chunk-size",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--chunk-size'" in result.stderr


def test_cli_command_tree_registration():
    command_names = {command.name for command in app.registered_commands}
    assert {
        "auth",
        "profile",
        "dv",
        "connector",
        "pages",
        "doctor",
        "env",
        "apps",
        "flows",
        "solution",
    }.issubset(command_names)
    dv_commands = {command.name for command in dataverse.app.registered_commands}
    assert {"whoami", "list", "get", "create", "update", "delete", "bulk-csv"}.issubset(dv_commands)
    assert hasattr(power_platform, "list_envs")


def test_cli_connector_push(monkeypatch, respx_mock, tmp_path):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    # Create a small openapi file
    p = tmp_path / "o.yaml"
    p.write_text("openapi: 3.0.3\ninfo:\n  title: t\n  version: 1\npaths: {}\n", encoding="utf-8")
    respx_mock.put(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"name": "myapi"}))
    result = runner.invoke(
        app,
        ["connector", "push", "--environment-id", "ENV", "--name", "myapi", "--openapi", str(p)],
    )
    assert result.exit_code == 0
    assert "myapi" in result.stdout
    assert respx_mock.calls, "expected connector request"
    auth_header = respx_mock.calls.last.request.headers.get("Authorization")
    assert auth_header == "Bearer dummy"
