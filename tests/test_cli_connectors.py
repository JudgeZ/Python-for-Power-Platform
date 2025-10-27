from __future__ import annotations

import importlib
import sys

import pytest
import typer

from pacx.errors import HttpError


class StubConnectorsClient:
    last_instance: StubConnectorsClient | None = None
    instances: list[StubConnectorsClient] = []

    def __init__(
        self,
        token_getter,
        *,
        use_connectivity: bool = False,
        client_request_id: str | None = None,
    ):
        self.token = token_getter()
        self.use_connectivity = use_connectivity
        self.client_request_id = client_request_id
        self.list_args: tuple[str, int | None] | None = None
        self.list_connectivity_args: tuple[str, int | None, str | None, str | None] | None = None
        self.iter_args: tuple[str, int | None] | None = None
        self.get_args: tuple[str, str] | None = None
        self.put_args: tuple[str, str, str | None] | None = None
        self.delete_args: tuple[str, str] | None = None
        self.validate_args: tuple[str, str, str, str | None] | None = None
        self.runtime_status_args: tuple[str, str] | None = None
        self.pages = [
            [{"name": "shared-api"}],
            [{"id": "custom-connector"}],
        ]
        StubConnectorsClient.last_instance = self
        StubConnectorsClient.instances.append(self)

    def list_apis(self, environment: str, *, top: int | None = None):
        if self.use_connectivity:
            return self.list_custom_connectors(environment, top=top)
        self.list_args = (environment, top)
        return {
            "value": [
                {"name": "shared-api"},
                {"id": "custom-connector"},
            ]
        }

    def list_custom_connectors(
        self,
        environment: str,
        *,
        top: int | None = None,
        skiptoken: str | None = None,
        filter_expression: str | None = None,
    ):
        self.list_connectivity_args = (environment, top, skiptoken, filter_expression)
        return {
            "value": [
                {"name": "arm-shared"},
                {"id": "arm-custom"},
            ]
        }

    def iter_apis(self, environment: str, *, top: int | None = None):
        self.iter_args = (environment, top)
        if self.use_connectivity:
            # Mirrors ConnectorsClient.iter_apis calling list_apis for the first page.
            self.list_apis(environment, top=top)
        yield from self.pages

    def get_api(self, environment: str, api_name: str):
        if self.use_connectivity:
            return self.get_custom_connector(environment, api_name)
        self.get_args = (environment, api_name)
        return {"name": api_name, "properties": {"displayName": "Sample Connector"}}

    def get_custom_connector(self, environment: str, api_name: str):
        self.get_args = (environment, api_name)
        return {"name": api_name, "properties": {"displayName": "ARM Connector"}}

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

    def delete_api(self, environment: str, api_name: str):
        if self.use_connectivity:
            return self.delete_custom_connector(environment, api_name)
        self.delete_args = (environment, api_name)
        return True

    def delete_custom_connector(self, environment: str, api_name: str):
        self.delete_args = (environment, api_name)
        return True

    def validate_custom_connector_from_openapi(
        self,
        environment: str,
        name: str,
        openapi_text: str,
        *,
        display_name: str | None = None,
    ):
        self.validate_args = (environment, name, openapi_text, display_name)
        return {"status": "Succeeded"}

    def validate_custom_connector(self, environment: str, name: str, payload: dict[str, object]):
        self.validate_args = (environment, name, "payload", None)
        return {"status": "Succeeded"}

    def get_custom_connector_runtime_status(self, environment: str, api_name: str):
        self.runtime_status_args = (environment, api_name)
        return {"availabilityState": "Healthy"}


@pytest.fixture(autouse=True)
def reset_stub():
    StubConnectorsClient.last_instance = None
    StubConnectorsClient.instances.clear()


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
    assert StubConnectorsClient.instances
    stub = StubConnectorsClient.instances[0]
    assert stub.use_connectivity is True
    assert stub.iter_args == ("ENV", 5)


def test_connectors_get_prints_payload(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", StubConnectorsClient)

    result = cli_runner.invoke(
        app,
        [
            "connector",
            "get",
            "--environment-id",
            "ENV",
            "--endpoint",
            "connectivity",
            "api-to-fetch",
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert "api-to-fetch" in result.stdout
    assert "ARM Connector" in result.stdout
    stub = StubConnectorsClient.last_instance
    assert stub.get_args == ("ENV", "api-to-fetch")


def test_connectors_delete_succeeds(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", StubConnectorsClient)

    result = cli_runner.invoke(
        app,
        [
            "connector",
            "delete",
            "--environment-id",
            "ENV",
            "--yes",
            "api-to-remove",
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert "Deleted connector 'api-to-remove'" in result.stdout
    stub = StubConnectorsClient.last_instance
    assert stub.use_connectivity is True
    assert stub.delete_args == ("ENV", "api-to-remove")


def test_connectors_delete_handles_404(monkeypatch, cli_runner):
    class FailingStub(StubConnectorsClient):
        def delete_api(self, environment: str, api_name: str):  # type: ignore[override]
            raise HttpError(404, "Not Found")

    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", FailingStub)

    result = cli_runner.invoke(
        app,
        [
            "connector",
            "delete",
            "--environment-id",
            "ENV",
            "--yes",
            "missing-api",
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 1
    assert "was not found" in result.stdout


def test_connectors_list_falls_back_on_missing_connectivity(monkeypatch, cli_runner):
    class MissingConnectivityStub(StubConnectorsClient):
        def list_apis(self, environment: str, *, top: int | None = None):  # type: ignore[override]
            if self.use_connectivity:
                raise HttpError(404, "Not Found")
            return super().list_apis(environment, top=top)

    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", MissingConnectivityStub)

    result = cli_runner.invoke(
        app,
        ["connector", "list", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert len(MissingConnectivityStub.instances) == 2
    assert MissingConnectivityStub.instances[0].use_connectivity is True
    assert MissingConnectivityStub.instances[1].use_connectivity is False


@pytest.mark.parametrize("status_code", [401, 403])
def test_connectors_list_falls_back_on_unauthorized_connectivity(
    monkeypatch, cli_runner, status_code
):
    class UnauthorizedConnectivityStub(StubConnectorsClient):
        def list_apis(self, environment: str, *, top: int | None = None):  # type: ignore[override]
            if self.use_connectivity:
                raise HttpError(status_code, "Forbidden")
            return super().list_apis(environment, top=top)

    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", UnauthorizedConnectivityStub)

    result = cli_runner.invoke(
        app,
        ["connector", "list", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert len(UnauthorizedConnectivityStub.instances) == 2
    assert UnauthorizedConnectivityStub.instances[0].use_connectivity is True
    assert UnauthorizedConnectivityStub.instances[1].use_connectivity is False


def test_connectors_validate_reads_definition(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", StubConnectorsClient)
    definition = tmp_path / "connector.yaml"
    definition.write_text("openapi: 3.0.3\npaths: {}\n", encoding="utf-8")

    result = cli_runner.invoke(
        app,
        [
            "connector",
            "validate",
            "--environment-id",
            "ENV",
            "--name",
            "sample",
            "--openapi",
            str(definition),
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    stub = StubConnectorsClient.last_instance
    assert stub is not None
    assert stub.validate_args == (
        "ENV",
        "sample",
        "openapi: 3.0.3\npaths: {}\n",
        None,
    )


def test_connectors_runtime_status(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.connectors.ConnectorsClient", StubConnectorsClient)

    result = cli_runner.invoke(
        app,
        [
            "connector",
            "runtime-status",
            "--environment-id",
            "ENV",
            "sample",
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert "Healthy" in result.stdout
    stub = StubConnectorsClient.last_instance
    assert stub.runtime_status_args == ("ENV", "sample")


def test_runtime_status_rejects_powerapps_endpoint(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)

    result = cli_runner.invoke(
        app,
        [
            "connector",
            "runtime-status",
            "--environment-id",
            "ENV",
            "--endpoint",
            "powerapps",
            "sample",
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code != 0
    assert "connectivity" in result.stdout.lower()
