from __future__ import annotations

import importlib
import sys

import pytest
from typer.testing import CliRunner

from pacx.models.app_management import ApplicationPackageOperation, ApplicationPackageSummary
from pacx.utils.poller import PollTimeoutError


class StubAppManagementClient:
    instances: list[StubAppManagementClient] = []
    wait_should_timeout: bool = False
    next_wait_status: str = "Succeeded"

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version or "2022-03-01-preview"
        self.list_calls: list[str | None] = []
        self.install_calls: list[tuple[str, str, dict[str, object]]] = []
        self.upgrade_calls: list[tuple[str, str, dict[str, object]]] = []
        self.status_calls: list[str] = []
        self.env_status_calls: list[tuple[str, str]] = []
        self.wait_calls: list[tuple[str | None, float, float]] = []
        StubAppManagementClient.instances.append(self)

    def list_tenant_packages(self) -> list[ApplicationPackageSummary]:
        self.list_calls.append(None)
        return [
            ApplicationPackageSummary(
                package_id="pkg-tenant",
                display_name="Tenant Package",
                version="1.0",
            )
        ]

    def list_environment_packages(self, environment_id: str) -> list[ApplicationPackageSummary]:
        self.list_calls.append(environment_id)
        return [
            ApplicationPackageSummary(
                package_id="pkg-env",
                environment_id=environment_id,
                display_name="Env Package",
                version="2.0",
            )
        ]

    def install_application_package(
        self,
        package_id: str,
        environment_id: str,
        *,
        parameters: dict[str, object] | None = None,
    ) -> object:
        self.install_calls.append((package_id, environment_id, parameters or {}))
        return object()

    def upgrade_environment_package(
        self,
        environment_id: str,
        package_id: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> object:
        self.upgrade_calls.append((environment_id, package_id, payload or {}))
        return object()

    def wait_for_operation(
        self,
        handle: object,
        *,
        environment_id: str | None = None,
        interval: float,
        timeout: float,
    ) -> ApplicationPackageOperation:
        if StubAppManagementClient.wait_should_timeout:
            StubAppManagementClient.wait_should_timeout = False
            raise PollTimeoutError(timeout, None)
        self.wait_calls.append((environment_id, interval, timeout))
        status = StubAppManagementClient.next_wait_status
        StubAppManagementClient.next_wait_status = "Succeeded"
        return ApplicationPackageOperation(operation_id="op-result", status=status)

    def get_install_status(self, operation_id: str) -> ApplicationPackageOperation:
        self.status_calls.append(operation_id)
        return ApplicationPackageOperation(operation_id=operation_id, status="Succeeded")

    def get_environment_operation_status(
        self, environment_id: str, operation_id: str
    ) -> ApplicationPackageOperation:
        self.env_status_calls.append((environment_id, operation_id))
        return ApplicationPackageOperation(operation_id=operation_id, status="Running")


def load_cli_app(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[CliRunner, object, type[StubAppManagementClient]]:
    for name in [mod for mod in list(sys.modules) if mod.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    monkeypatch.setattr(module, "AppManagementClient", StubAppManagementClient)
    monkeypatch.setattr("pacx.cli.app_management.AppManagementClient", StubAppManagementClient)
    StubAppManagementClient.instances = []
    StubAppManagementClient.wait_should_timeout = False
    StubAppManagementClient.next_wait_status = "Succeeded"
    return CliRunner(), module.app, StubAppManagementClient


@pytest.fixture
def cli_setup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "token")
    return load_cli_app(monkeypatch)


def test_list_packages_tenant(cli_setup):
    runner, app, client_cls = cli_setup

    result = runner.invoke(app, ["app", "pkgs", "list"])

    assert result.exit_code == 0
    assert "Tenant Package" in result.stdout
    assert client_cls.instances[0].list_calls == [None]


def test_list_packages_environment(cli_setup):
    runner, app, client_cls = cli_setup

    result = runner.invoke(app, ["app", "pkgs", "list", "--environment-id", "env-1"])

    assert result.exit_code == 0
    assert "Env Package" in result.stdout
    assert client_cls.instances[0].list_calls == ["env-1"]


def test_install_package_success(cli_setup):
    runner, app, client_cls = cli_setup

    result = runner.invoke(
        app,
        ["app", "pkgs", "install", "pkg-1", "--environment-id", "env-1"],
    )

    assert result.exit_code == 0
    assert "Install completed" in result.stdout
    client = client_cls.instances[0]
    assert client.install_calls == [("pkg-1", "env-1", {})]
    assert client.wait_calls == [("env-1", 2.0, 600.0)]


def test_install_package_timeout(cli_setup):
    runner, app, client_cls = cli_setup
    client_cls.wait_should_timeout = True

    result = runner.invoke(
        app,
        ["app", "pkgs", "install", "pkg-1", "--environment-id", "env-1", "--timeout", "0.1"],
    )

    assert result.exit_code == 1
    assert "Install timed out" in result.stdout


def test_upgrade_package_success(cli_setup):
    runner, app, client_cls = cli_setup

    result = runner.invoke(
        app,
        ["app", "pkgs", "upgrade", "pkg-1", "--environment-id", "env-1"],
    )

    assert result.exit_code == 0
    assert "Upgrade completed" in result.stdout
    client = client_cls.instances[0]
    assert client.upgrade_calls == [("env-1", "pkg-1", {})]
    assert client.wait_calls == [("env-1", 2.0, 600.0)]


def test_status_tenant(cli_setup):
    runner, app, client_cls = cli_setup

    result = runner.invoke(app, ["app", "pkgs", "status", "op-1"])

    assert result.exit_code == 0
    assert "Status completed" in result.stdout
    assert client_cls.instances[0].status_calls == ["op-1"]


def test_status_environment(cli_setup):
    runner, app, client_cls = cli_setup

    result = runner.invoke(app, ["app", "pkgs", "status", "op-1", "--environment-id", "env-1"])

    assert result.exit_code == 0
    assert "Status in progress" in result.stdout
    assert client_cls.instances[0].env_status_calls == [("env-1", "op-1")]


def test_install_package_failure(cli_setup):
    runner, app, client_cls = cli_setup
    client_cls.next_wait_status = "Failed"

    result = runner.invoke(
        app,
        ["app", "pkgs", "install", "pkg-1", "--environment-id", "env-1"],
    )

    assert result.exit_code == 1
    assert "Install failed" in result.stdout
    assert "operation=op-result" in result.stdout


def test_upgrade_package_canceled(cli_setup):
    runner, app, client_cls = cli_setup
    client_cls.next_wait_status = "Canceled"

    result = runner.invoke(
        app,
        ["app", "pkgs", "upgrade", "pkg-1", "--environment-id", "env-1"],
    )

    assert result.exit_code == 1
    assert "Upgrade failed" in result.stdout
