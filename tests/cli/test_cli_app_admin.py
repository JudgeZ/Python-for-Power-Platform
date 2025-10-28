from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from typing import Any

import pytest
from typer.testing import CliRunner

from pacx.clients.environment_management import EnvironmentOperationHandle
from pacx.clients.power_apps_admin import AdminOperationHandle, PowerAppsAdminClient
from pacx.models.environment_management import EnvironmentLifecycleOperation, EnvironmentListPage
from pacx.models.power_platform import AppListPage, AppSummary, AppVersionList, EnvironmentSummary


@dataclass
class StubHandle:
    operation_location: str | None = "https://example/op"
    retry_after: int | None = None


class StubAdminClient:
    instances: list[StubAdminClient] = []

    def __init__(self, token_getter, api_version: str):
        self.token = token_getter()
        self.api_version = api_version
        self.list_calls: list[dict[str, Any]] = []
        self.show_calls: list[tuple[str, str]] = []
        self.version_calls: list[tuple[str, str]] = []
        self.share_payloads: list[dict[str, Any]] = []
        self.revoke_payloads: list[dict[str, Any]] = []
        self.owner_payloads: list[dict[str, Any]] = []
        StubAdminClient.instances.append(self)

    def list_apps(self, env: str, **kwargs: Any):
        self.list_calls.append({"environment_id": env, **kwargs})
        return AppListPage.model_validate(
            {
                "value": [
                    {
                        "id": "app1",
                        "displayName": "Sample App",
                        "environmentId": env,
                    }
                ]
            }
        )

    def get_app(self, environment_id: str, app_id: str):
        self.show_calls.append((environment_id, app_id))
        return AppSummary.model_validate(
            {
                "id": app_id,
                "displayName": "Sample App",
                "environmentId": environment_id,
            }
        )

    def list_app_versions(self, environment_id: str, app_id: str, **kwargs: Any):
        self.version_calls.append((environment_id, app_id))
        return AppVersionList.model_validate(
            {
                "value": [
                    {
                        "versionId": "1.0.0",
                        "description": "Initial",
                    }
                ]
            }
        )

    def restore_app(self, environment_id: str, app_id: str, payload: dict[str, Any]):
        return AdminOperationHandle("https://example/op")

    publish_app = restore_app

    def share_app(self, environment_id: str, app_id: str, request):
        self.share_payloads.append(request.to_payload())
        return AdminOperationHandle("https://example/op")

    def revoke_share(self, environment_id: str, app_id: str, request):
        self.revoke_payloads.append(request.to_payload())
        return AdminOperationHandle("https://example/op")

    def set_owner(self, environment_id: str, app_id: str, request):
        self.owner_payloads.append(request.to_payload())
        return AdminOperationHandle("https://example/op")

    def list_permissions(self, environment_id: str, app_id: str):
        return []

    share_principals_from_dict = staticmethod(PowerAppsAdminClient.share_principals_from_dict)


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    for name in [module for module in list(sys.modules) if module.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    monkeypatch.setattr(
        "pacx.cli.app_management.PowerAppsAdminClient",
        StubAdminClient,
    )
    StubAdminClient.instances = []
    return module.app


runner = CliRunner()


def test_list_admin_apps(cli_app):
    result = runner.invoke(cli_app, ["app", "admin", "list", "env"])
    assert result.exit_code == 0
    assert "Sample App" in result.stdout
    client = StubAdminClient.instances[-1]
    assert client.list_calls


def test_share_admin_app(cli_app):
    principals = json.dumps(
        {"principals": [{"id": "user", "principalType": "User", "roleName": "CanView"}]}
    )
    result = runner.invoke(
        cli_app,
        [
            "app",
            "admin",
            "share",
            "env",
            "app1",
            "--principals",
            principals,
        ],
    )
    assert result.exit_code == 0
    client = StubAdminClient.instances[-1]
    assert client.share_payloads == [
        {
            "principals": [
                {
                    "id": "user",
                    "principalType": "User",
                    "roleName": "CanView",
                }
            ]
        }
    ]


def test_revoke_admin_access(cli_app):
    result = runner.invoke(
        cli_app,
        [
            "app",
            "admin",
            "revoke",
            "env",
            "app1",
            "--principal-ids",
            json.dumps(["user"]),
        ],
    )
    assert result.exit_code == 0
    client = StubAdminClient.instances[-1]
    assert client.revoke_payloads == [{"principalIds": ["user"]}]


class StubEnvironmentClient:
    instances: list[StubEnvironmentClient] = []

    def __init__(self, token_getter, api_version: str):
        self.token = token_getter()
        self.api_version = api_version
        self.list_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []
        self.group_list_called = False
        self.operations_calls: list[str] = []
        self.create_payloads: list[dict[str, Any]] = []
        self.copy_payloads: list[dict[str, Any]] = []
        self.reset_payloads: list[dict[str, Any]] = []
        self.backup_payloads: list[dict[str, Any]] = []
        self.restore_payloads: list[dict[str, Any]] = []
        self.enable_calls: list[str] = []
        self.disable_calls: list[str] = []
        self.group_create_payloads: list[dict[str, Any]] = []
        self.group_update_payloads: list[tuple[str, dict[str, Any]]] = []
        self.group_delete_calls: list[str] = []
        self.group_add_calls: list[tuple[str, str]] = []
        self.group_remove_calls: list[tuple[str, str]] = []
        self._environments = EnvironmentListPage.model_validate(
            {
                "value": [
                    {
                        "id": "env1",
                        "name": "Env One",
                        "type": "Production",
                    }
                ]
            }
        )
        StubEnvironmentClient.instances.append(self)

    def list_environments(self, **kwargs: Any) -> EnvironmentListPage:
        self.list_calls.append(kwargs)
        return self._environments

    def get_environment(self, environment_id: str) -> EnvironmentSummary:
        return EnvironmentSummary.model_validate(
            {
                "id": environment_id,
                "name": "Env One",
                "type": "Production",
            }
        )

    def delete_environment(self, environment_id: str, **_: Any) -> EnvironmentOperationHandle:
        self.delete_calls.append(environment_id)
        operation = EnvironmentLifecycleOperation(operation_id="op-delete", status="InProgress")
        return EnvironmentOperationHandle("https://example/ops/delete", operation=operation)

    def create_environment(self, request, *, validate_only: bool | None = None):
        self.create_payloads.append({"payload": request, "validate_only": validate_only})
        operation = EnvironmentLifecycleOperation(operation_id="op-create", status="Accepted")
        return EnvironmentOperationHandle("https://example/ops/create", operation=operation)

    def copy_environment(self, environment_id: str, request):
        self.copy_payloads.append({"env": environment_id, "payload": request})
        return EnvironmentOperationHandle("https://example/ops/copy", operation=None)

    def reset_environment(self, environment_id: str, request):
        self.reset_payloads.append({"env": environment_id, "payload": request})
        return EnvironmentOperationHandle("https://example/ops/reset", operation=None)

    def backup_environment(self, environment_id: str, request):
        self.backup_payloads.append({"env": environment_id, "payload": request})
        return EnvironmentOperationHandle("https://example/ops/backup", retry_after=15)

    def restore_environment(self, environment_id: str, request):
        self.restore_payloads.append({"env": environment_id, "payload": request})
        return EnvironmentOperationHandle("https://example/ops/restore", operation=None)

    def enable_managed_environment(self, environment_id: str):
        self.enable_calls.append(environment_id)
        return EnvironmentOperationHandle("https://example/ops/enable", operation=None)

    def disable_managed_environment(self, environment_id: str):
        self.disable_calls.append(environment_id)
        return EnvironmentOperationHandle("https://example/ops/disable", operation=None)

    def list_environment_groups(self) -> list[dict[str, Any]]:
        self.group_list_called = True
        return [{"id": "group1", "displayName": "Group One"}]

    def get_environment_group(self, environment_group_id: str) -> dict[str, Any]:
        return {"id": environment_group_id, "displayName": "Group One"}

    def create_environment_group(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.group_create_payloads.append(payload)
        return {"id": "group1", **payload}

    def update_environment_group(
        self, environment_group_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.group_update_payloads.append((environment_group_id, payload))
        return {"id": environment_group_id, **payload}

    def delete_environment_group(self, environment_group_id: str):
        self.group_delete_calls.append(environment_group_id)
        return EnvironmentOperationHandle("https://example/ops/delete-group", operation=None)

    def add_environment_to_group(self, environment_group_id: str, environment_id: str):
        self.group_add_calls.append((environment_group_id, environment_id))
        return EnvironmentOperationHandle("https://example/ops/group-add", operation=None)

    def remove_environment_from_group(self, environment_group_id: str, environment_id: str):
        self.group_remove_calls.append((environment_group_id, environment_id))
        return EnvironmentOperationHandle("https://example/ops/group-remove", operation=None)

    def list_operations(self, environment_id: str):
        self.operations_calls.append(environment_id)
        return [EnvironmentLifecycleOperation(operation_id="op1", status="Running")]

    def get_operation(self, operation_id: str):
        return EnvironmentLifecycleOperation(operation_id=operation_id, status="Succeeded")


@pytest.fixture
def environment_cli_app(monkeypatch: pytest.MonkeyPatch):
    for name in [
        module for module in list(sys.modules) if module.startswith("pacx.cli.environment")
    ]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli.environment")
    monkeypatch.setattr("pacx.cli.environment.EnvironmentManagementClient", StubEnvironmentClient)
    StubEnvironmentClient.instances = []
    return module.app


def _register_environment_cli_tests() -> None:

    def test_environment_cli_list(environment_cli_app):
        local_runner = CliRunner()
        result = local_runner.invoke(
            environment_cli_app,
            ["list"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert result.exit_code == 0
        assert "Env One" in result.stdout
        client = StubEnvironmentClient.instances[-1]
        assert client.list_calls

    def test_environment_cli_delete(environment_cli_app):
        local_runner = CliRunner()
        result = local_runner.invoke(
            environment_cli_app,
            ["delete", "env1"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert result.exit_code == 0
        client = StubEnvironmentClient.instances[-1]
        assert client.delete_calls == ["env1"]

    def test_environment_cli_groups(environment_cli_app):
        local_runner = CliRunner()
        result = local_runner.invoke(
            environment_cli_app,
            ["groups", "list"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert result.exit_code == 0
        client = StubEnvironmentClient.instances[-1]
        assert client.group_list_called

    def test_environment_cli_create_and_show(environment_cli_app):
        local_runner = CliRunner()
        payload = json.dumps(
            {
                "displayName": "New Env",
                "region": "unitedstates",
                "environmentSku": "Sandbox",
            }
        )
        create = local_runner.invoke(
            environment_cli_app,
            ["create", "--payload", payload],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert create.exit_code == 0
        create_stub = StubEnvironmentClient.instances[-1]
        show = local_runner.invoke(
            environment_cli_app,
            ["show", "env1"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert show.exit_code == 0 and "Env One" in show.stdout
        assert create_stub.create_payloads

    def test_environment_cli_copy_reset_backup_restore(environment_cli_app):
        local_runner = CliRunner()
        copy_payload = json.dumps(
            {
                "targetEnvironmentName": "Clone",
                "targetEnvironmentRegion": "us",
            }
        )
        reset_payload = json.dumps({"resetType": "Soft"})
        restore_payload = json.dumps({"backupId": "00000000-0000-0000-0000-000000000000"})
        backup_payload = json.dumps({"label": "Nightly"})

        for command in [
            ["copy", "env1", "--payload", copy_payload],
            ["reset", "env1", "--payload", reset_payload],
            ["backup", "env1", "--payload", backup_payload],
            ["restore", "env1", "--payload", restore_payload],
        ]:
            local_runner.invoke(
                environment_cli_app,
                command,
                env={"PACX_ACCESS_TOKEN": "token"},
            )

        assert any(client.copy_payloads for client in StubEnvironmentClient.instances)
        assert any(client.reset_payloads for client in StubEnvironmentClient.instances)
        assert any(client.backup_payloads for client in StubEnvironmentClient.instances)
        assert any(client.restore_payloads for client in StubEnvironmentClient.instances)

    def test_environment_cli_enable_disable(environment_cli_app):
        local_runner = CliRunner()
        local_runner.invoke(
            environment_cli_app,
            ["enable-managed", "env1"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        local_runner.invoke(
            environment_cli_app,
            ["disable-managed", "env1"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert any(client.enable_calls for client in StubEnvironmentClient.instances)
        assert any(client.disable_calls for client in StubEnvironmentClient.instances)

    def test_environment_cli_operations(environment_cli_app):
        local_runner = CliRunner()
        ops = local_runner.invoke(
            environment_cli_app,
            ["ops", "list", "env1"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert ops.exit_code == 0 and "op1" in ops.stdout
        show = local_runner.invoke(
            environment_cli_app,
            ["ops", "show", "op1"],
            env={"PACX_ACCESS_TOKEN": "token"},
        )
        assert show.exit_code == 0 and "Succeeded" in show.stdout
        assert any(
            client.operations_calls == ["env1"] for client in StubEnvironmentClient.instances
        )

    def test_environment_cli_group_management(environment_cli_app):
        local_runner = CliRunner()
        create_payload = json.dumps({"displayName": "Group"})
        update_payload = json.dumps({"displayName": "Group Updated"})
        for command in [
            ["groups", "show", "group1"],
            ["groups", "create", "--payload", create_payload],
            ["groups", "update", "group1", "--payload", update_payload],
            ["groups", "delete", "group1"],
            ["groups", "add", "group1", "env1"],
            ["groups", "remove", "group1", "env1"],
        ]:
            local_runner.invoke(
                environment_cli_app,
                command,
                env={"PACX_ACCESS_TOKEN": "token"},
            )
        assert any(client.group_create_payloads for client in StubEnvironmentClient.instances)
        assert any(client.group_update_payloads for client in StubEnvironmentClient.instances)
        assert any(client.group_delete_calls for client in StubEnvironmentClient.instances)
        assert any(client.group_add_calls for client in StubEnvironmentClient.instances)
        assert any(client.group_remove_calls for client in StubEnvironmentClient.instances)

    globals().update(locals())


_register_environment_cli_tests()
