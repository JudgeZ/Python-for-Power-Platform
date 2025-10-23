from __future__ import annotations

import importlib
import sys

import pytest
import typer


class StubConnectorsClient:
    last_instance: "StubConnectorsClient | None" = None

    def __init__(self, token_getter):
        self.token = token_getter()
        self.list_args: tuple[str, int | None] | None = None
        self.get_args: tuple[str, str] | None = None
        self.put_args: tuple[str, str, str | None] | None = None
        StubConnectorsClient.last_instance = self

    def list_apis(self, environment: str, *, top: int | None = None):
        self.list_args = (environment, top)
        return {
            "value": [
                {"name": "shared-api"},
                {"id": "custom-connector"},
            ]
        }

    def get_api(self, environment: str, api_name: str):
        self.get_args = (environment, api_name)
        return {"name": api_name, "properties": {"displayName": "Sample Connector"}}

    def put_api_from_openapi(
        self,
        environment: str,
        name: str,
        openapi_text: str,
        *,
        display_name: str | None = None,
    ):
        self.put_args = (environment, name, display_name)
        return {"name": name, "status": "updated"}


@pytest.fixture(autouse=True)
def reset_stub():
    StubConnectorsClient.last_instance = None


def load_cli_app(monkeypatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


def test_connectors_list_formats_output(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", StubConnectorsClient)

    result = cli_runner.invoke(
        app,
        ["connector", "list", "--environment-id", "ENV", "--top", "5"],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "shared-api"
    assert lines[1] == "custom-connector"
    stub = StubConnectorsClient.last_instance
    assert stub is not None
    assert stub.list_args == ("ENV", 5)


def test_connectors_get_prints_payload(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", StubConnectorsClient)

    result = cli_runner.invoke(
        app,
        ["connector", "get", "--environment-id", "ENV", "api-to-fetch"],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert "api-to-fetch" in result.stdout
    assert "Sample Connector" in result.stdout
    stub = StubConnectorsClient.last_instance
    assert stub is not None
    assert stub.get_args == ("ENV", "api-to-fetch")
