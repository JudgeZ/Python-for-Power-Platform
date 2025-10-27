import importlib
import json
import sys

import pytest
import typer
from typer.testing import CliRunner

from pacx.clients.policy import PolicyOperationHandle, PolicyPage
from pacx.models.policy import AsyncOperation, ConnectorGroup, ConnectorReference, DataLossPreventionPolicy, PolicyAssignment


class StubPolicyClient:
    instances: list["StubPolicyClient"] = []

    def __init__(self, token_getter, api_version: str = "2023-10-01-preview") -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.list_calls: list[tuple[int | None, int | None]] = []
        self.get_calls: list[str] = []
        self.create_payloads: list[dict[str, object]] = []
        self.update_payloads: list[tuple[str, dict[str, object]]] = []
        self.delete_calls: list[str] = []
        self.connector_updates: list[tuple[str, list[dict[str, object]]]] = []
        self.assignment_updates: list[tuple[str, list[dict[str, object]]]] = []
        self.assignment_removals: list[tuple[str, str]] = []
        self.wait_calls: list[tuple[str, float, float]] = []
        StubPolicyClient.instances.append(self)

    def list_policies(self, *, top: int | None = None, skip: int | None = None) -> PolicyPage:
        self.list_calls.append((top, skip))
        policies = [
            DataLossPreventionPolicy(
                id="policy-1",
                display_name="Policy One",
                state="Active",
                policy_scope="Tenant",
            )
        ]
        return PolicyPage(policies, next_link=None)

    def get_policy(self, policy_id: str) -> DataLossPreventionPolicy:
        self.get_calls.append(policy_id)
        return DataLossPreventionPolicy(
            id=policy_id,
            display_name="Policy One",
            state="Active",
            policy_scope="Tenant",
        )

    def create_policy(self, policy: DataLossPreventionPolicy) -> PolicyOperationHandle:
        self.create_payloads.append(policy.model_dump(by_alias=True, exclude_none=True))
        return PolicyOperationHandle(
            "https://example/operations/create",
            AsyncOperation(operation_id="create-op", status="Running"),
        )

    def update_policy(
        self, policy_id: str, policy: DataLossPreventionPolicy
    ) -> PolicyOperationHandle:
        self.update_payloads.append((policy_id, policy.model_dump(by_alias=True, exclude_none=True)))
        return PolicyOperationHandle(
            "https://example/operations/update",
            AsyncOperation(operation_id="update-op", status="Running"),
        )

    def delete_policy(self, policy_id: str) -> PolicyOperationHandle:
        self.delete_calls.append(policy_id)
        return PolicyOperationHandle(
            "https://example/operations/delete",
            AsyncOperation(operation_id="delete-op", status="Running"),
        )

    def list_connector_groups(self, policy_id: str) -> list[ConnectorGroup]:
        return [
            ConnectorGroup(
                classification="Business",
                connectors=[ConnectorReference(id="shared-office365")],
            )
        ]

    def update_connector_groups(
        self, policy_id: str, groups: list[ConnectorGroup]
    ) -> PolicyOperationHandle:
        payload = [group.model_dump(by_alias=True, exclude_none=True) for group in groups]
        self.connector_updates.append((policy_id, payload))
        return PolicyOperationHandle(
            "https://example/operations/connectors",
            AsyncOperation(operation_id="connectors-op", status="Running"),
        )

    def list_assignments(self, policy_id: str) -> list[PolicyAssignment]:
        return [
            PolicyAssignment(
                assignment_id="assign-1",
                environment_id="Default-123",
                assignment_type="Include",
            )
        ]

    def assign_policy(
        self, policy_id: str, assignments: list[PolicyAssignment]
    ) -> PolicyOperationHandle:
        payload = [assignment.model_dump(by_alias=True, exclude_none=True) for assignment in assignments]
        self.assignment_updates.append((policy_id, payload))
        return PolicyOperationHandle(
            "https://example/operations/assign",
            AsyncOperation(operation_id="assign-op", status="Running"),
        )

    def remove_assignment(self, policy_id: str, assignment_id: str) -> PolicyOperationHandle:
        self.assignment_removals.append((policy_id, assignment_id))
        return PolicyOperationHandle(
            "https://example/operations/remove",
            AsyncOperation(operation_id="remove-op", status="Running"),
        )

    def wait_for_operation(
        self, operation_url: str, *, interval: float = 2.0, timeout: float = 600.0
    ) -> AsyncOperation:
        self.wait_calls.append((operation_url, interval, timeout))
        return AsyncOperation(operation_id="wait-op", status="Succeeded")


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)

    for name in [module for module in sys.modules if module.startswith("pacx.cli")]:
        sys.modules.pop(name)

    module = importlib.import_module("pacx.cli")
    monkeypatch.setattr(module.policy, "DataLossPreventionClient", StubPolicyClient)
    monkeypatch.setattr("pacx.cli.policy.DataLossPreventionClient", StubPolicyClient)
    StubPolicyClient.instances = []
    return module.app, StubPolicyClient


def test_policy_list_outputs_summary(cli_runner, cli_app):
    app, client_cls = cli_app

    result = cli_runner.invoke(app, ["policy", "dlp", "list"])

    assert result.exit_code == 0
    assert "Policy One" in result.stdout
    assert client_cls.instances
    assert client_cls.instances[0].list_calls == [(None, None)]


def test_policy_create_waits_for_completion(cli_runner, cli_app):
    app, client_cls = cli_app

    payload = json.dumps({"displayName": "Draft Policy", "state": "Draft"})
    result = cli_runner.invoke(
        app,
        ["policy", "dlp", "create", "--payload", payload, "--wait"],
    )

    assert result.exit_code == 0
    instance = client_cls.instances[0]
    assert instance.create_payloads[0]["displayName"] == "Draft Policy"
    assert instance.wait_calls
    assert "Policy creation completed" in result.stdout


def test_policy_connectors_update_records_payload(cli_runner, cli_app):
    app, client_cls = cli_app
    payload = json.dumps(
        {
            "groups": [
                {
                    "classification": "Business",
                    "connectors": [{"id": "shared-office365"}],
                }
            ]
        }
    )

    result = cli_runner.invoke(
        app,
        ["policy", "dlp", "connectors", "update", "policy-1", "--payload", payload],
    )

    assert result.exit_code == 0
    instance = client_cls.instances[0]
    assert instance.connector_updates == [
        (
            "policy-1",
            [
                {
                    "classification": "Business",
                    "connectors": [{"id": "shared-office365"}],
                }
            ],
        )
    ]


def test_policy_assign_command_posts_assignments(cli_runner, cli_app):
    app, client_cls = cli_app
    payload = json.dumps(
        {
            "assignments": [
                {"environmentId": "Default-123", "assignmentType": "Include"}
            ]
        }
    )

    result = cli_runner.invoke(
        app,
        ["policy", "dlp", "assignments", "assign", "policy-1", "--payload", payload, "--wait"],
    )

    assert result.exit_code == 0
    instance = client_cls.instances[0]
    assert instance.assignment_updates == [
        (
            "policy-1",
            [{"environmentId": "Default-123", "assignmentType": "Include"}],
        )
    ]
    assert instance.wait_calls


def test_policy_scope_requirement(cli_app, monkeypatch: pytest.MonkeyPatch):
    from pacx.config import ConfigData, Profile

    app, client_cls = cli_app
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    config = ConfigData(
        default_profile="default",
        profiles={
            "default": Profile(
                name="default",
                tenant_id="tenant",
                client_id="client",
                scope="https://api.powerplatform.com/.default",
            )
        },
    )

    monkeypatch.setattr("pacx.cli.policy.get_config_from_context", lambda ctx: config)
    monkeypatch.setattr("pacx.cli.policy.get_token_getter", lambda ctx: (lambda: "token"))

    runner = CliRunner()
    result = runner.invoke(app, ["policy", "dlp", "list"], env={})

    assert result.exit_code != 0
    assert "Policy.DataLossPrevention.Read" in result.stderr
    assert not client_cls.instances
