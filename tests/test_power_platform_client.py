from __future__ import annotations

import httpx

from pacx.clients.power_platform import PowerPlatformClient


def build_client(token_getter):
    return PowerPlatformClient(token_getter)


def test_list_environments(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200, json={"value": [{"id": "env1", "name": "Env One", "environmentType": "Sandbox", "location": "US"}]}
        )
    )
    envs = client.list_environments()
    assert route.called
    assert len(envs) == 1
    assert envs[0].id == "env1"
    assert envs[0].name == "Env One"


def test_get_environment(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments/env1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"id": "env1", "name": "Env One"}))

    env = client.get_environment("env1")

    assert env.id == "env1"
    assert env.name == "Env One"


def test_delete_environment_with_validation_flag(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.delete(
        "https://api.powerplatform.com/environmentmanagement/environments/env1",
        params={"api-version": "2022-03-01-preview", "ValidateOnly": "true"},
    ).mock(return_value=httpx.Response(204))

    client.delete_environment("env1", validate_only=True)

    assert route.called


def test_list_environment_settings(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/settings",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"setting": "value"}))

    settings = client.list_environment_settings("env1")

    assert settings == {"setting": "value"}


def test_upsert_environment_setting(respx_mock, token_getter):
    client = build_client(token_getter)
    body = {"setting": "value"}
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/settings",
        params={"api-version": "2022-03-01-preview"},
        json=body,
    ).mock(return_value=httpx.Response(200))

    client.upsert_environment_setting("env1", body)

    assert route.called


def test_list_apps_with_paging(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/env1/apps",
        params={"api-version": "2022-03-01-preview", "$top": 5, "$skiptoken": "next"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "app1", "name": "App One"},
                    {"id": "app2", "name": "App Two"},
                ]
            },
        )
    )

    apps = client.list_apps("env1", top=5, skiptoken="next")

    assert route.called
    assert [app.id for app in apps] == ["app1", "app2"]


def test_list_cloud_flows_filters_none_filtered(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows",
        params={"api-version": "2022-03-01-preview", "status": "Active"},
    ).mock(return_value=httpx.Response(200, json={"value": [{"id": "flow1", "name": "Flow"}]}))

    flows = client.list_cloud_flows("env1", status="Active", owner=None)

    assert route.called
    assert flows[0].id == "flow1"


def test_list_flow_runs(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/flowRuns",
        params={"api-version": "2022-03-01-preview", "workflowId": "flow1"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={"value": [{"id": "run1", "name": "Run", "status": "Succeeded", "startTime": "s", "endTime": "e"}]},
        )
    )

    runs = client.list_flow_runs("env1", "flow1")

    assert route.called
    assert runs[0].id == "run1"
    assert runs[0].status == "Succeeded"
