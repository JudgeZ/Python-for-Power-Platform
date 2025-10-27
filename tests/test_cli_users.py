from __future__ import annotations

import importlib
import sys

import pytest
import typer

from pacx.clients.user_management import UserManagementOperationHandle
from pacx.models.user_management import (
    AdminRoleAssignment,
    AdminRoleAssignmentList,
    AsyncOperationStatus,
)


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


class StubUserManagementClient:
    instances: list["StubUserManagementClient"] = []

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.apply_calls: list[str] = []
        self.remove_calls: list[tuple[str, str]] = []
        self.list_calls: list[str] = []
        self.wait_calls: list[tuple[str, float, float]] = []
        StubUserManagementClient.instances.append(self)

    def apply_admin_role(self, user_id: str) -> UserManagementOperationHandle:
        self.apply_calls.append(user_id)
        return UserManagementOperationHandle(
            "https://example/operations/op-apply", {"id": "op-apply"}
        )

    def remove_admin_role(
        self, user_id: str, role_definition_id: str
    ) -> UserManagementOperationHandle:
        self.remove_calls.append((user_id, role_definition_id))
        return UserManagementOperationHandle(
            "https://example/operations/op-remove", {"id": "op-remove"}
        )

    def list_admin_roles(self, user_id: str) -> AdminRoleAssignmentList:
        self.list_calls.append(user_id)
        assignment = AdminRoleAssignment(
            role_definition_id="role-1", role_display_name="Power Platform admin", scope="tenant"
        )
        return AdminRoleAssignmentList(value=[assignment])

    def wait_for_operation(
        self, operation_url: str, *, interval: float, timeout: float
    ) -> AsyncOperationStatus:
        self.wait_calls.append((operation_url, interval, timeout))
        return AsyncOperationStatus(status="Succeeded", percent_complete=100)


@pytest.fixture
def users_cli(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli_app(monkeypatch)
    monkeypatch.setattr(module, "UserManagementClient", StubUserManagementClient)
    monkeypatch.setattr("pacx.cli.users.UserManagementClient", StubUserManagementClient)
    StubUserManagementClient.instances = []
    return app, StubUserManagementClient


def test_apply_admin_role_waits_for_completion(cli_runner, users_cli) -> None:
    app, client_cls = users_cli

    result = cli_runner.invoke(
        app,
        ["users", "admin-role", "apply", "user-1"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    instance = client_cls.instances[-1]
    assert instance.apply_calls == ["user-1"]
    assert instance.wait_calls
    url, interval, timeout = instance.wait_calls[0]
    assert url.endswith("op-apply")
    assert interval == 2.0
    assert timeout == 600.0


def test_apply_admin_role_supports_no_wait(cli_runner, users_cli) -> None:
    app, client_cls = users_cli

    result = cli_runner.invoke(
        app,
        ["users", "admin-role", "apply", "user-1", "--no-wait"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    instance = client_cls.instances[-1]
    assert instance.apply_calls == ["user-1"]
    assert instance.wait_calls == []


def test_remove_admin_role_passes_role_definition(cli_runner, users_cli) -> None:
    app, client_cls = users_cli

    result = cli_runner.invoke(
        app,
        [
            "users",
            "admin-role",
            "remove",
            "user-1",
            "--role-definition-id",
            "role-1",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    instance = client_cls.instances[-1]
    assert instance.remove_calls == [("user-1", "role-1")]


def test_list_admin_roles_prints_assignments(cli_runner, users_cli) -> None:
    app, _ = users_cli

    result = cli_runner.invoke(
        app,
        ["users", "admin-role", "list", "user-1"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "Power Platform admin" in result.stdout
    assert "role-1" in result.stdout
