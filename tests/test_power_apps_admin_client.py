from __future__ import annotations

import httpx

from pacx.clients.power_apps_admin import PowerAppsAdminClient
from pacx.models.power_platform import ShareAppRequest, SharePrincipal


def build_client(token_getter):
    return PowerAppsAdminClient(token_getter)


def test_list_apps_returns_models(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/env/apps",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "app1",
                        "displayName": "Sample App",
                        "environmentId": "env",
                    }
                ],
                "continuationToken": "token",
            },
        )
    )

    page = client.list_apps("env")

    assert route.called
    assert [app.id for app in page.value] == ["app1"]
    assert page.continuation_token == "token"  # noqa: S105


def test_share_app_submits_payload(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    request = ShareAppRequest(
        principals=[
            SharePrincipal(id="user", principalType="User", roleName="CanView"),
        ],
        notify_share_targets=True,
    )
    route = respx_mock.post(
        "https://api.powerplatform.com/powerapps/environments/env/apps/app:share",
        params={"api-version": "2022-03-01-preview"},
        json={
            "principals": [
                {
                    "id": "user",
                    "principalType": "User",
                    "roleName": "CanView",
                }
            ],
            "notifyShareTargets": True,
        },
    ).mock(return_value=httpx.Response(202, headers={"Operation-Location": "https://example/op"}))

    handle = client.share_app("env", "app", request)

    assert route.called
    assert handle.operation_location == "https://example/op"


def test_list_permissions_returns_assignments(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/env/apps/app/permissions",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "perm1",
                        "roleName": "CanEdit",
                        "principalType": "User",
                    }
                ]
            },
        )
    )

    permissions = client.list_permissions("env", "app")

    assert route.called
    assert [perm.role_name for perm in permissions] == ["CanEdit"]
