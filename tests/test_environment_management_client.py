from __future__ import annotations

import httpx

from pacx.clients.environment_management import EnvironmentManagementClient
from pacx.models.environment_management import (
    EnvironmentBackupRequest,
    EnvironmentCopyRequest,
    EnvironmentCreateRequest,
    EnvironmentResetRequest,
    EnvironmentRestoreRequest,
)


def build_client(token_getter):
    return EnvironmentManagementClient(token_getter)


def test_list_environments_returns_models(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "env1",
                        "name": "Env One",
                        "type": "Production",
                    }
                ],
                "continuationToken": "token",
            },
        )
    )

    page = client.list_environments()

    assert route.called
    assert [env.id for env in page.value] == ["env1"]
    assert page.continuation_token == "token"  # noqa: S105


def test_create_environment_posts_payload(monkeypatch, token_getter) -> None:
    client = build_client(token_getter)
    request = EnvironmentCreateRequest(
        display_name="New Env",
        region="unitedstates",
        environment_sku="Sandbox",
    )

    captured: dict[str, object] = {}

    def fake_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = kwargs.get("params")
        captured["json"] = kwargs.get("json")
        url = f"https://api.powerplatform.com/{path.lstrip('/')}"
        return httpx.Response(
            202,
            headers={"Operation-Location": "https://example/ops/1"},
            json={"operationId": "op1", "status": "InProgress"},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(client.http, "request", fake_request)

    handle = client.create_environment(request, validate_only=False)

    assert captured["method"] == "POST"
    assert captured["path"] == "environmentmanagement/environments"
    params = captured["params"]
    assert isinstance(params, dict)
    assert params["validateOnly"] is False
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["displayName"] == "New Env"
    assert payload["region"] == "unitedstates"
    assert payload["environmentSku"] == "Sandbox"
    assert payload.get("additionalSettings") == {}
    assert handle.operation_location == "https://example/ops/1"
    assert handle.operation and handle.operation.operation_id == "op1"


def test_backup_environment_returns_handle(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    request = EnvironmentBackupRequest(label="Nightly")
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:backup",
        params={"api-version": "2022-03-01-preview"},
        json={"label": "Nightly"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://example/ops/2", "Retry-After": "30"},
            json={"operationId": "op2", "status": "Accepted"},
        )
    )

    handle = client.backup_environment("env1", request)

    assert route.called
    assert handle.retry_after == 30
    assert handle.operation and handle.operation.status == "Accepted"


def test_environment_copy_reset_restore(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    copy_route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:copy",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://example/ops/copy"},
            json={"operationId": "copy-op"},
        )
    )
    reset_route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:reset",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://example/ops/reset"},
            json={"operationId": "reset-op"},
        )
    )
    restore_route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:restore",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://example/ops/restore"},
            json={"operationId": "restore-op"},
        )
    )

    copy_handle = client.copy_environment(
        "env1",
        EnvironmentCopyRequest(
            target_environment_name="Clone",
            target_environment_region="us",
        ),
    )
    reset_handle = client.reset_environment(
        "env1",
        EnvironmentResetRequest(reset_type="Soft"),
    )
    restore_handle = client.restore_environment(
        "env1",
        EnvironmentRestoreRequest(backup_id="00000000-0000-0000-0000-000000000000"),
    )

    assert copy_route.called and copy_handle.operation_location
    assert reset_route.called and reset_handle.operation_location
    assert restore_route.called and restore_handle.operation_location


def test_environment_operations_and_groups(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    list_ops_route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/operations",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"operationId": "op1", "status": "InProgress"},
                ]
            },
        )
    )
    get_op_route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/operations/op1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"operationId": "op1", "status": "Succeeded"}))
    list_groups_route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"value": [{"id": "group1"}]}))
    create_group_route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(201, json={"id": "group1"}))
    delete_group_route = respx_mock.delete(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(202, json={}))

    operations = client.list_operations("env1")
    operation = client.get_operation("op1")
    groups = client.list_environment_groups()
    new_group = client.create_environment_group({"displayName": "Example"})
    delete_handle = client.delete_environment_group("group1")

    assert list_ops_route.called and operations[0].operation_id == "op1"
    assert get_op_route.called and operation.status == "Succeeded"
    assert list_groups_route.called and groups[0]["id"] == "group1"
    assert create_group_route.called and new_group["id"] == "group1"
    assert delete_group_route.called and delete_handle.operation_location is None


def test_environment_managed_flags(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    enable_route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/managedGovernance/enable",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(202, json={"operationId": "enable"}))
    disable_route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/managedGovernance/disable",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(202, json={"operationId": "disable"}))

    enable_handle = client.enable_managed_environment("env1")
    disable_handle = client.disable_managed_environment("env1")

    assert enable_route.called and enable_handle.operation_location is None
    assert disable_route.called and disable_handle.operation_location is None
