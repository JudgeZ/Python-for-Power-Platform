from __future__ import annotations

import importlib
import json
import sys
import types

import pytest
import typer


class StubDataverseClient:
    last_instance: StubDataverseClient | None = None

    def __init__(self, token_getter, host: str | None = None) -> None:
        self.token = token_getter()
        self.host = host
        self.list_args: dict[str, object] | None = None
        self.create_args: tuple[str, dict[str, object]] | None = None
        self.update_args: tuple[str, str, dict[str, object]] | None = None
        self.delete_args: tuple[str, str] | None = None
        self.get_args: tuple[str, str] | None = None
        StubDataverseClient.last_instance = self

    def whoami(self) -> dict[str, str]:
        return {"user": "tester"}

    def list_records(
        self,
        entityset: str,
        *,
        select: str | None = None,
        filter: str | None = None,
        top: int | None = None,
        orderby: str | None = None,
    ) -> dict[str, object]:
        self.list_args = {
            "entityset": entityset,
            "select": select,
            "filter": filter,
            "top": top,
            "orderby": orderby,
        }
        return {"value": [{"name": "row"}]}

    def get_record(self, entityset: str, record_id: str) -> dict[str, str]:
        self.get_args = (entityset, record_id)
        return {"id": record_id, "entityset": entityset}

    def create_record(self, entityset: str, payload: dict[str, object]) -> dict[str, object]:
        self.create_args = (entityset, payload)
        return {"id": "created", **payload}

    def update_record(self, entityset: str, record_id: str, payload: dict[str, object]) -> None:
        self.update_args = (entityset, record_id, payload)

    def delete_record(self, entityset: str, record_id: str) -> None:
        self.delete_args = (entityset, record_id)


@pytest.fixture(autouse=True)
def reset_dataverse_stub() -> None:
    StubDataverseClient.last_instance = None


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.dataverse.DataverseClient", StubDataverseClient)
    return app


def test_dataverse_whoami(monkeypatch: pytest.MonkeyPatch, cli_runner, cli_app) -> None:
    result = cli_runner.invoke(
        cli_app,
        ["dv", "whoami"],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert result.exit_code == 0
    assert "tester" in result.stdout
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.host == "example.crm.dynamics.com"


def test_dataverse_crud_operations(cli_runner, cli_app) -> None:
    payload = {"name": "Sample"}
    result = cli_runner.invoke(
        cli_app,
        [
            "dv",
            "create",
            "accounts",
            "--data",
            json.dumps(payload),
        ],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert result.exit_code == 0
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.create_args == ("accounts", payload)

    result_get = cli_runner.invoke(
        cli_app,
        ["dv", "get", "accounts", "12345"],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert result_get.exit_code == 0
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.get_args == ("accounts", "12345")

    result_update = cli_runner.invoke(
        cli_app,
        ["dv", "update", "accounts", "12345", "--data", json.dumps({"name": "Updated"})],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert result_update.exit_code == 0
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.update_args == ("accounts", "12345", {"name": "Updated"})

    result_delete = cli_runner.invoke(
        cli_app,
        ["dv", "delete", "accounts", "12345"],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert result_delete.exit_code == 0
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.delete_args == ("accounts", "12345")


def test_dataverse_list_and_bulk_csv(monkeypatch: pytest.MonkeyPatch, cli_runner, cli_app, tmp_path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id,name\n1,Alice\n", encoding="utf-8")
    report_file = tmp_path / "report.csv"

    stub_result = types.SimpleNamespace(
        operations=[
            types.SimpleNamespace(
                row_index=1,
                content_id="1",
                status_code=200,
                reason="OK",
                json=None,
            )
        ],
        stats=types.SimpleNamespace(successes=1, failures=0, retry_invocations=0),
    )

    monkeypatch.setattr(
        "pacx.cli.dataverse.bulk_csv_upsert",
        lambda *args, **kwargs: stub_result,
    )

    list_result = cli_runner.invoke(
        cli_app,
        ["dv", "list", "accounts", "--select", "name"],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert list_result.exit_code == 0
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.list_args == {
        "entityset": "accounts",
        "select": "name",
        "filter": None,
        "top": None,
        "orderby": None,
    }

    bulk_result = cli_runner.invoke(
        cli_app,
        [
            "dv",
            "bulk-csv",
            "accounts",
            str(csv_file),
            "--id-column",
            "id",
            "--report",
            str(report_file),
        ],
        env={"PACX_ACCESS_TOKEN": "token", "DATAVERSE_HOST": "example.crm.dynamics.com"},
    )
    assert bulk_result.exit_code == 0
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "row_index" in content
