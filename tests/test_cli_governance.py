from __future__ import annotations

import importlib
import sys
from typing import Any

import pytest
import typer

from pacx.clients.governance import GovernanceOperation


class StubGovernanceClient:
    instances: list[StubGovernanceClient] = []

    def __init__(self, token_getter, api_version: str = "2022-03-01-preview") -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.report_payloads: list[dict[str, Any]] = []
        self.wait_calls: list[tuple[str, float, float]] = []
        self.assignment_calls: list[dict[str, Any]] = []
        self.list_filters: list[dict[str, Any]] = []
        StubGovernanceClient.instances.append(self)

    def create_cross_tenant_connection_report(self, payload: dict[str, Any]) -> GovernanceOperation:
        self.report_payloads.append(payload)
        return GovernanceOperation(
            "https://example/governance/crossTenantConnectionReports/report-123",
            {"id": "report-123", "status": "Running"},
        )

    def wait_for_report(self, report_id: str, *, interval: float, timeout: float) -> dict[str, Any]:
        self.wait_calls.append((report_id, interval, timeout))
        return {"id": report_id, "status": "Completed"}

    def list_rule_assignments(
        self,
        *,
        environment_id: str | None = None,
        environment_group_id: str | None = None,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        self.list_filters.append(
            {
                "environment_id": environment_id,
                "environment_group_id": environment_group_id,
                "policy_id": policy_id,
            }
        )
        return {"value": []}

    def create_environment_assignment(self, policy_id: str, environment_id: str) -> GovernanceOperation:
        self.assignment_calls.append(
            {
                "policy_id": policy_id,
                "environment_id": environment_id,
                "type": "environment",
            }
        )
        return GovernanceOperation("https://example/assignments/env", {"status": "Accepted"})

    def create_environment_group_assignment(
        self, policy_id: str, environment_group_id: str
    ) -> GovernanceOperation:
        self.assignment_calls.append(
            {
                "policy_id": policy_id,
                "environment_group_id": environment_group_id,
                "type": "group",
            }
        )
        return GovernanceOperation("https://example/assignments/group", {"status": "Accepted"})


@pytest.fixture(autouse=True)
def reset_stub() -> None:
    StubGovernanceClient.instances = []


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for name in [module for module in sys.modules if module.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    return module.app


def test_report_submit_polls_when_requested(monkeypatch: pytest.MonkeyPatch, cli_runner) -> None:
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.governance.GovernanceClient", StubGovernanceClient)

    result = cli_runner.invoke(
        app,
        [
            "governance",
            "report",
            "submit",
            "--payload",
            '{"scope": "All"}',
            "--poll",
            "--interval",
            "0",
            "--timeout",
            "1",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    stub = StubGovernanceClient.instances[0]
    assert stub.report_payloads == [{"scope": "All"}]
    assert stub.wait_calls == [("report-123", 0.0, 1.0)]
    assert "Completed" in result.stdout


def test_assignment_list_passes_filters(monkeypatch: pytest.MonkeyPatch, cli_runner) -> None:
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.governance.GovernanceClient", StubGovernanceClient)

    result = cli_runner.invoke(
        app,
        [
            "governance",
            "assignment",
            "list",
            "--environment-id",
            "env-1",
            "--policy-id",
            "policy-9",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    stub = StubGovernanceClient.instances[0]
    assert stub.list_filters == [
        {"environment_id": "env-1", "environment_group_id": None, "policy_id": "policy-9"}
    ]


def test_assignment_create_targets_environment(monkeypatch: pytest.MonkeyPatch, cli_runner) -> None:
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.governance.GovernanceClient", StubGovernanceClient)

    result = cli_runner.invoke(
        app,
        [
            "governance",
            "assignment",
            "create",
            "--policy-id",
            "policy-1",
            "--environment-id",
            "env-5",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    stub = StubGovernanceClient.instances[0]
    assert stub.assignment_calls == [
        {"policy_id": "policy-1", "environment_id": "env-5", "type": "environment"}
    ]


def test_assignment_create_requires_single_target(monkeypatch: pytest.MonkeyPatch, cli_runner) -> None:
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.governance.GovernanceClient", StubGovernanceClient)

    result = cli_runner.invoke(
        app,
        [
            "governance",
            "assignment",
            "create",
            "--policy-id",
            "policy-1",
            "--environment-id",
            "env-5",
            "--environment-group-id",
            "group-1",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code != 0
    output = result.stderr or result.stdout
    assert "Provide exactly one" in output
