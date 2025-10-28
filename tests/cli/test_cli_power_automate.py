from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import Any

import pytest

from pacx.models.power_automate import CloudFlowPage
from pacx.models.power_platform import CloudFlow


def load_cli(monkeypatch: pytest.MonkeyPatch):
    for name in [module for module in list(sys.modules) if module.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    return module.app, module


@dataclass
class _StateCall:
    environment_id: str
    flow_id: str
    payload: Any


class StubPowerAutomateClient:
    instances: list[StubPowerAutomateClient] = []
    list_result: CloudFlowPage = CloudFlowPage()
    flow_result: CloudFlow = CloudFlow(id="flow-1")

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.list_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_calls: list[tuple[str, str]] = []
        self.state_calls: list[_StateCall] = []
        self.delete_calls: list[tuple[str, str]] = []
        StubPowerAutomateClient.instances.append(self)

    def __enter__(self) -> StubPowerAutomateClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - signature matches context manager
        return None

    def close(self) -> None:  # pragma: no cover - compatibility shim
        return None

    def list_cloud_flows(self, environment_id: str, **filters: Any) -> CloudFlowPage:
        self.list_calls.append((environment_id, filters))
        return self.list_result

    def get_cloud_flow(self, environment_id: str, flow_id: str) -> CloudFlow:
        self.get_calls.append((environment_id, flow_id))
        return self.flow_result

    def set_cloud_flow_state(self, environment_id: str, flow_id: str, payload: Any) -> CloudFlow:
        self.state_calls.append(_StateCall(environment_id, flow_id, payload))
        return self.flow_result

    def delete_cloud_flow(self, environment_id: str, flow_id: str) -> None:
        self.delete_calls.append((environment_id, flow_id))


@pytest.fixture
def flows_cli(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli(monkeypatch)
    cli_module = importlib.import_module("pacx.cli.power_automate")
    monkeypatch.setattr(module.power_automate, "PowerAutomateClient", StubPowerAutomateClient)
    monkeypatch.setattr(cli_module, "PowerAutomateClient", StubPowerAutomateClient)
    StubPowerAutomateClient.instances = []
    StubPowerAutomateClient.list_result = CloudFlowPage(
        flows=[CloudFlow(id="flow-1", properties={"displayName": "Sample Flow"})],
        continuation_token="token-1",  # noqa: S106
    )
    StubPowerAutomateClient.flow_result = CloudFlow(
        id="flow-1", properties={"state": "Started", "displayName": "Sample Flow"}
    )
    return app, StubPowerAutomateClient


def test_list_flows_prints_results_and_token(cli_runner, flows_cli) -> None:
    app, client_cls = flows_cli

    result = cli_runner.invoke(app, ["flows", "list", "env-1"])

    assert result.exit_code == 0, result.stdout
    assert "Sample Flow" in result.stdout
    assert "token-1" in result.stdout
    client = client_cls.instances[-1]
    assert client.list_calls
    env_id, filters = client.list_calls[-1]
    assert env_id == "env-1"
    assert {k: v for k, v in filters.items() if v is not None} == {}


def test_set_state_normalises_input(cli_runner, flows_cli) -> None:
    app, client_cls = flows_cli

    result = cli_runner.invoke(
        app,
        ["flows", "set-state", "env-1", "flow-1", "--state", "started"],
    )

    assert result.exit_code == 0, result.stdout
    client = client_cls.instances[-1]
    assert len(client.state_calls) == 1
    call = client.state_calls[0]
    assert call.environment_id == "env-1"
    assert call.flow_id == "flow-1"
    payload = call.payload.to_payload() if hasattr(call.payload, "to_payload") else call.payload
    assert payload == {"state": "Started"}


def test_delete_flow_honours_yes_flag(cli_runner, flows_cli) -> None:
    app, client_cls = flows_cli

    result = cli_runner.invoke(
        app,
        ["flows", "delete", "env-1", "flow-1", "--yes"],
    )

    assert result.exit_code == 0, result.stdout
    client = client_cls.instances[-1]
    assert ("env-1", "flow-1") in client.delete_calls
