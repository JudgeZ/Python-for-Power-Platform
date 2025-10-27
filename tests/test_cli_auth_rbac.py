from __future__ import annotations

import importlib
import json
import sys

import pytest
import typer

from pacx.models.authorization import RoleAssignment, RoleDefinition, RolePermission


class StubAuthorizationClient:
    last_instance: StubAuthorizationClient | None = None
    role_definitions: list[RoleDefinition] = []
    role_assignments: list[RoleAssignment] = []

    def __init__(self, token_getter):
        self.token = token_getter()
        self.created_role_definition: dict[str, object] | None = None
        self.updated_role_definition: tuple[str, dict[str, object]] | None = None
        self.deleted_role_definition: str | None = None
        self.list_assignment_filters: tuple[str | None, str | None] | None = None
        self.created_assignment: dict[str, object] | None = None
        self.deleted_assignment: str | None = None
        StubAuthorizationClient.last_instance = self

    @staticmethod
    def _to_dict(payload: object) -> dict[str, object]:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(by_alias=True, exclude_none=True)  # type: ignore[no-any-return]
        if isinstance(payload, dict):
            return payload  # type: ignore[return-value]
        raise TypeError(f"Unsupported payload type: {type(payload)!r}")

    def list_role_definitions(self) -> list[RoleDefinition]:
        return list(self.role_definitions)

    def create_role_definition(self, payload):
        data = self._to_dict(payload)
        self.created_role_definition = data
        return RoleDefinition(
            id=data.get("id", "role-created"),
            name=str(data.get("name", "new-role")),
            permissions=[RolePermission()],
            assignable_scopes=list(data.get("assignableScopes", [])),
        )

    def update_role_definition(self, role_id: str, payload):
        data = self._to_dict(payload)
        self.updated_role_definition = (role_id, data)
        return RoleDefinition(
            id=role_id,
            name="updated-role",
            permissions=[RolePermission()],
            assignable_scopes=list(data.get("assignableScopes", [])),
        )

    def delete_role_definition(self, role_id: str) -> None:
        self.deleted_role_definition = role_id

    def list_role_assignments(self, *, principal_id: str | None = None, scope: str | None = None):
        self.list_assignment_filters = (principal_id, scope)
        return list(self.role_assignments)

    def create_role_assignment(self, payload):
        data = self._to_dict(payload)
        self.created_assignment = data
        return RoleAssignment(
            id="assignment-created",
            principal_id=str(data.get("principalId")),
            role_definition_id=str(data.get("roleDefinitionId")),
            scope=str(data.get("scope")),
        )

    def delete_role_assignment(self, assignment_id: str) -> None:
        self.deleted_assignment = assignment_id


@pytest.fixture(autouse=True)
def reset_stub():
    StubAuthorizationClient.last_instance = None
    StubAuthorizationClient.role_definitions = []
    StubAuthorizationClient.role_assignments = []


def load_cli_app(monkeypatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in list(sys.modules) if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


def test_roles_list_prints_roles(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.auth.AuthorizationRbacClient", StubAuthorizationClient)
    StubAuthorizationClient.role_definitions = [
        RoleDefinition(
            id="role1",
            name="Support",
            permissions=[RolePermission()],
            assignable_scopes=["/scopes/default"],
        ),
        RoleDefinition(
            id="role2",
            name="Maker",
            permissions=[RolePermission()],
            assignable_scopes=[],
        ),
    ]

    result = cli_runner.invoke(app, ["auth", "roles", "list"])

    assert result.exit_code == 0
    assert "Support" in result.stdout
    assert "Maker" in result.stdout


def test_roles_create_reads_payload_file(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.auth.AuthorizationRbacClient", StubAuthorizationClient)
    payload = {
        "name": "Custom",
        "permissions": [{"actions": ["*"], "notActions": []}],
        "assignableScopes": ["/scopes/custom"],
    }
    path = tmp_path / "role.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = cli_runner.invoke(app, ["auth", "roles", "create", "--definition", str(path)])

    assert result.exit_code == 0
    stub = StubAuthorizationClient.last_instance
    assert stub is not None
    expected_payload = {
        "name": "Custom",
        "permissions": [
            {
                "actions": ["*"],
                "notActions": [],
                "dataActions": [],
                "notDataActions": [],
            }
        ],
        "assignableScopes": ["/scopes/custom"],
    }
    assert stub.created_role_definition == expected_payload


def test_assignments_list_forwards_filters(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.auth.AuthorizationRbacClient", StubAuthorizationClient)
    StubAuthorizationClient.role_assignments = [
        RoleAssignment(
            id="assign1",
            principal_id="principal",
            role_definition_id="role1",
            scope="/scopes/default",
        )
    ]

    result = cli_runner.invoke(
        app,
        [
            "auth",
            "assignments",
            "list",
            "--principal-id",
            "principal",
            "--scope",
            "/scopes/default",
        ],
    )

    assert result.exit_code == 0
    stub = StubAuthorizationClient.last_instance
    assert stub is not None
    assert stub.list_assignment_filters == ("principal", "/scopes/default")
    assert "role1" in result.stdout


def test_assignments_create_uses_options(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.auth.AuthorizationRbacClient", StubAuthorizationClient)

    result = cli_runner.invoke(
        app,
        [
            "auth",
            "assignments",
            "create",
            "--principal-id",
            "principal",
            "--role-definition-id",
            "role1",
            "--scope",
            "/scopes/default",
        ],
    )

    assert result.exit_code == 0
    stub = StubAuthorizationClient.last_instance
    assert stub is not None
    assert stub.created_assignment == {
        "principalId": "principal",
        "roleDefinitionId": "role1",
        "scope": "/scopes/default",
    }


def test_assignments_delete_skips_prompt_with_yes(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.auth.AuthorizationRbacClient", StubAuthorizationClient)

    result = cli_runner.invoke(
        app,
        ["auth", "assignments", "delete", "--yes", "assignment-id"],
    )

    assert result.exit_code == 0
    stub = StubAuthorizationClient.last_instance
    assert stub is not None
    assert stub.deleted_assignment == "assignment-id"
