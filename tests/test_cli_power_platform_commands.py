from __future__ import annotations

import importlib
import sys
from typing import Iterable

import pytest
import typer


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
        StubPowerPlatformClient.instances.append(self)

    def list_environments(self) -> Iterable[StubEnvironment]:
        return [StubEnvironment("env-1"), StubEnvironment("env-2", location="eu")]

    def list_apps(self, environment_id: str) -> Iterable[StubSummary]:
        self.apps_calls.append(environment_id)
        return [StubSummary("app-1"), StubSummary("app-2")]

    def list_cloud_flows(self, environment_id: str) -> Iterable[StubSummary]:
        self.flows_calls.append(environment_id)
        return [StubSummary("flow-1")]


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
