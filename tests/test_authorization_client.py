from __future__ import annotations

import json

import httpx

from pacx.clients.authorization import AuthorizationRbacClient
from pacx.models.authorization import (
    CreateRoleAssignmentRequest,
    CreateRoleDefinitionRequest,
    RolePermission,
    UpdateRoleDefinitionRequest,
)


def build_client(token_getter):
    return AuthorizationRbacClient(token_getter)


def test_list_role_definitions(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/authorization/rbac/roleDefinitions",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "role1",
                        "name": "Support",
                        "assignableScopes": ["/providers/Microsoft.PowerPlatform/scopes/default"],
                        "permissions": [{"actions": ["*"], "notActions": []}],
                    }
                ]
            },
        )
    )

    roles = client.list_role_definitions()

    assert route.called
    assert len(roles) == 1
    assert roles[0].name == "Support"
    assert roles[0].assignable_scopes == ["/providers/Microsoft.PowerPlatform/scopes/default"]


def test_create_role_definition_payload_schema(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/authorization/rbac/roleDefinitions",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "role2",
                "name": "Custom",
                "assignableScopes": ["/scopes/one"],
                "permissions": [{"actions": ["resource.read"], "notActions": []}],
            },
        )
    )

    request = CreateRoleDefinitionRequest(
        name="Custom",
        description="Custom role",
        permissions=[RolePermission(actions=["resource.read"])],
        assignable_scopes=["/scopes/one"],
    )

    role = client.create_role_definition(request)

    assert route.called
    sent = json.loads(route.calls.last.request.content.decode())
    assert sent == {
        "name": "Custom",
        "description": "Custom role",
        "permissions": [
            {
                "actions": ["resource.read"],
                "notActions": [],
                "dataActions": [],
                "notDataActions": [],
            }
        ],
        "assignableScopes": ["/scopes/one"],
    }
    assert role.id == "role2"


def test_update_role_definition_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.patch(
        "https://api.powerplatform.com/authorization/rbac/roleDefinitions/role2",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "role2",
                "name": "Custom",
                "assignableScopes": ["/scopes/two"],
                "permissions": [{"actions": ["resource.read"], "notActions": []}],
            },
        )
    )

    request = UpdateRoleDefinitionRequest(assignable_scopes=["/scopes/two"])
    client.update_role_definition("role2", request)

    assert route.called
    sent = json.loads(route.calls.last.request.content.decode())
    assert sent == {"assignableScopes": ["/scopes/two"]}


def test_list_role_assignments_filters(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/authorization/rbac/roleAssignments",
        params={
            "api-version": "2022-03-01-preview",
            "principalId": "principal",
            "scope": "/scopes/one",
        },
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "assign1",
                        "principalId": "principal",
                        "roleDefinitionId": "role1",
                        "scope": "/scopes/one",
                    }
                ]
            },
        )
    )

    assignments = client.list_role_assignments(principal_id="principal", scope="/scopes/one")

    assert route.called
    assert assignments[0].role_definition_id == "role1"


def test_create_role_assignment_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/authorization/rbac/roleAssignments",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "assign1",
                "principalId": "principal",
                "roleDefinitionId": "role1",
                "scope": "/scopes/one",
            },
        )
    )

    request = CreateRoleAssignmentRequest(
        principal_id="principal", role_definition_id="role1", scope="/scopes/one"
    )
    assignment = client.create_role_assignment(request)

    assert route.called
    sent = json.loads(route.calls.last.request.content.decode())
    assert sent == {
        "principalId": "principal",
        "roleDefinitionId": "role1",
        "scope": "/scopes/one",
    }
    assert assignment.id == "assign1"


def test_delete_role_assignment(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.delete(
        "https://api.powerplatform.com/authorization/rbac/roleAssignments/assign1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(204))

    client.delete_role_assignment("assign1")

    assert route.called
