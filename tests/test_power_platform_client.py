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


def test_list_apps_paginates_until_exhausted(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/env1/apps",
    ).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "value": [{"id": "app1", "name": "App One"}],
                    "@odata.nextLink": "https://api.powerplatform.com/powerapps/environments/env1/apps?$skiptoken=token&api-version=2022-03-01-preview",
                },
            ),
            httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "app2", "name": "App Two"},
                        {"id": "app3", "name": "App Three"},
                    ]
                },
            ),
        ]
    )

    apps = client.list_apps("env1")

    assert route.called
    assert len(route.calls) == 2
    assert route.calls[0].request.url.params["api-version"] == "2022-03-01-preview"
    assert route.calls[1].request.url.params["$skiptoken"] == "token"
    assert [app.id for app in apps] == ["app1", "app2", "app3"]


def test_list_cloud_flows_aggregates_pages(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows",
    ).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "value": [{"id": "flow1", "name": "Flow One"}],
                    "@odata.nextLink": "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows?$skiptoken=more&api-version=2022-03-01-preview",
                },
            ),
            httpx.Response(
                200,
                json={"value": [{"id": "flow2", "name": "Flow Two"}]},
            ),
        ]
    )

    flows = client.list_cloud_flows("env1", status="Active", owner=None)

    assert route.called
    assert len(route.calls) == 2
    first_request_params = route.calls[0].request.url.params
    assert first_request_params["api-version"] == "2022-03-01-preview"
    assert first_request_params["status"] == "Active"
    assert [flow.id for flow in flows] == ["flow1", "flow2"]


def test_list_flow_runs_aggregates_workflow_pages(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/flowRuns",
    ).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "run1",
                            "name": "Run One",
                            "status": "Succeeded",
                            "startTime": "s",
                            "endTime": "e",
                        }
                    ],
                    "workflowRun@odata.nextLink": "https://api.powerplatform.com/powerautomate/environments/env1/flowRuns?$skiptoken=next&api-version=2022-03-01-preview",
                },
            ),
            httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "run2",
                            "name": "Run Two",
                            "status": "Failed",
                            "startTime": "s2",
                            "endTime": "e2",
                        }
                    ]
                },
            ),
        ]
    )

    runs = client.list_flow_runs("env1", "flow1")

    assert route.called
    assert len(route.calls) == 2
    assert route.calls[0].request.url.params["workflowId"] == "flow1"
    assert [run.id for run in runs] == ["run1", "run2"]
