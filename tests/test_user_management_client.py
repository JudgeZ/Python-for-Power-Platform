from __future__ import annotations

import json

import httpx

from pacx.clients.user_management import UserManagementClient


def build_client(token_getter):
    return UserManagementClient(token_getter)


def test_apply_admin_role_returns_operation_handle(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/usermanagement/users/user-1:applyAdminRole",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://api.powerplatform.com/usermanagement/operations/op-1"},
            json={"status": "Running"},
        )
    )

    handle = client.apply_admin_role("user-1")

    assert route.called
    assert handle.operation_location == "https://api.powerplatform.com/usermanagement/operations/op-1"
    assert handle.operation_id == "op-1"
    assert handle.metadata["status"] == "Running"


def test_remove_admin_role_serializes_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/usermanagement/users/user-1:removeAdminRole",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://api.powerplatform.com/usermanagement/operations/op-2"},
            json={"status": "NotStarted"},
        )
    )

    handle = client.remove_admin_role("user-1", "role-123")

    assert route.called
    payload = json.loads(route.calls[0].request.content.decode())
    assert payload == {"roleDefinitionId": "role-123"}
    assert handle.operation_id == "op-2"


def test_list_admin_roles_parses_assignments(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/usermanagement/users/user-1/adminRoles",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "assign-1",
                        "roleDefinitionId": "role-123",
                        "roleDisplayName": "Power Platform admin",
                        "scope": "tenant",
                    }
                ]
            },
        )
    )

    assignments = client.list_admin_roles("user-1")

    assert len(assignments.value) == 1
    item = assignments.value[0]
    assert item.role_definition_id == "role-123"
    assert item.role_display_name == "Power Platform admin"


def test_get_operation_returns_status(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/usermanagement/operations/op-3",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={"id": "op-3", "status": "Succeeded", "percentComplete": 100},
        )
    )

    status = client.get_operation("op-3")

    assert status.id == "op-3"
    assert status.status == "Succeeded"
    assert status.percent_complete == 100


def test_wait_for_operation_polls_until_terminal_state(respx_mock, token_getter, monkeypatch):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/usermanagement/operations/op-4",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running", "percentComplete": 50}),
            httpx.Response(200, json={"status": "Succeeded", "percentComplete": 100}),
        ]
    )
    monkeypatch.setattr("pacx.utils.poller.time.sleep", lambda _: None)

    status = client.wait_for_operation(
        "https://api.powerplatform.com/usermanagement/operations/op-4",
        interval=0.01,
        timeout=10,
    )

    assert route.called
    assert len(route.calls) == 2
    assert status.status == "Succeeded"
    assert status.percent_complete == 100
