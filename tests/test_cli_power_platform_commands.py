from __future__ import annotations

import importlib
import sys
from typing import Iterable

import importlib
import sys
from typing import Iterable

import pytest
import typer

from pacx.clients.power_platform import OperationHandle


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app, module


class StubEnvironment:
    def __init__(self, name: str, type: str = "Production", location: str = "us") -> None:
        self.name = name
        self.type = type
        self.location = location
        self.id = name


class StubSummary:
    def __init__(self, identifier: str) -> None:
        self.name = identifier
        self.id = identifier


class StubPowerPlatformClient:
    instances: list["StubPowerPlatformClient"] = []

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.apps_calls: list[str] = []
        self.flows_calls: list[str] = []
        self.copy_calls: list[tuple[str, dict[str, object]]] = []
        self.reset_calls: list[tuple[str, dict[str, object]]] = []
        self.backup_calls: list[tuple[str, dict[str, object]]] = []
        self.restore_calls: list[tuple[str, dict[str, object]]] = []
        self.apply_calls: list[tuple[str, str]] = []
        self.revoke_calls: list[tuple[str, str]] = []
        StubPowerPlatformClient.instances.append(self)

    def list_environments(self) -> Iterable[StubEnvironment]:
        return [StubEnvironment("env-1"), StubEnvironment("env-2", location="eu")]

    def list_apps(self, environment_id: str) -> Iterable[StubSummary]:
        self.apps_calls.append(environment_id)
        return [StubSummary("app-1"), StubSummary("app-2")]

    def list_cloud_flows(self, environment_id: str) -> Iterable[StubSummary]:
        self.flows_calls.append(environment_id)
        return [StubSummary("flow-1")]

    def copy_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.copy_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/copy", {"status": "Accepted"})

    def reset_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.reset_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/reset", {})

    def backup_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.backup_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/backup", {})

    def restore_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.restore_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/restore", {})

    def list_environment_groups(self) -> list[dict[str, object]]:
        return [{"id": "group-1"}]

    def get_environment_group(self, group_id: str) -> dict[str, object]:
        return {"id": group_id}

    def create_environment_group(self, payload: dict[str, object]) -> dict[str, object]:
        return {"id": "group-created", **payload}

    def update_environment_group(self, group_id: str, payload: dict[str, object]) -> dict[str, object]:
        return {"id": group_id, **payload}

    def delete_environment_group(self, group_id: str) -> OperationHandle:
        return OperationHandle(f"https://example/groups/{group_id}/operations/delete", {})

    def apply_environment_group(self, group_id: str, environment_id: str) -> OperationHandle:
        self.apply_calls.append((group_id, environment_id))
        return OperationHandle("https://example/operations/apply", {})

    def revoke_environment_group(self, group_id: str, environment_id: str) -> OperationHandle:
        self.revoke_calls.append((group_id, environment_id))
        return OperationHandle("https://example/operations/revoke", {})


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli_app(monkeypatch)
    monkeypatch.setattr(module, "PowerPlatformClient", StubPowerPlatformClient)
    monkeypatch.setattr("pacx.cli.power_platform.PowerPlatformClient", StubPowerPlatformClient)
    StubPowerPlatformClient.instances = []
    return app, StubPowerPlatformClient


def test_list_environments(cli_runner, cli_app) -> None:
    app, _ = cli_app
    result = cli_runner.invoke(
        app,
        ["env"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result.exit_code == 0
    assert "env-1" in result.stdout
    assert "env-2" in result.stdout


def test_list_apps_and_flows(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result_apps = cli_runner.invoke(
        app,
        ["apps", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_apps.exit_code == 0
    assert "app-1" in result_apps.stdout
    assert "app-2" in result_apps.stdout

    result_flows = cli_runner.invoke(
        app,
        ["flows", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_flows.exit_code == 0
    assert "flow-1" in result_flows.stdout
    assert any(instance.apps_calls for instance in client_cls.instances)


def test_environment_copy_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["env", "copy", "--environment-id", "ENV", "--payload", "{}"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert any(instance.copy_calls for instance in client_cls.instances)


def test_environment_group_apply(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["env-group", "apply", "group-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert any(instance.apply_calls for instance in client_cls.instances)
