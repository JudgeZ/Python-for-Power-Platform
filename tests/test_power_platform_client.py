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
            200,
            json={
                "value": [
                    {
                        "id": "env1",
                        "name": "Env One",
                        "environmentType": "Sandbox",
                        "location": "US",
                    }
                ]
            },
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


def test_list_app_versions_returns_page(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1/versions",
        params={
            "api-version": "2022-03-01-preview",
            "$top": "5",
            "$skiptoken": "cursor",
        },
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {"id": "ver1", "versionId": "1.0", "description": "Initial"},
                    {"id": "ver2", "versionId": "1.1"},
                ],
                "nextLink": "https://api.powerplatform.com/.../versions?$skiptoken=more",
                "continuationToken": "more",
            },
        ),
    )

    page = client.list_app_versions("env1", "app1", top=5, skiptoken="cursor")

    assert route.called
    assert [v.version_id for v in page.versions] == ["1.0", "1.1"]
    assert page.next_link
    assert page.continuation_token == "more"  # noqa: S105


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


def test_get_cloud_flow(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"id": "flow1", "name": "My Flow"}))

    flow = client.get_cloud_flow("env1", "flow1")

    assert flow.id == "flow1"
    assert flow.name == "My Flow"


def test_update_cloud_flow_state(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.patch(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1",
        params={"api-version": "2022-03-01-preview"},
        json={"state": "Started"},
    ).mock(return_value=httpx.Response(200, json={"properties": {"state": "Started"}}))

    flow = client.update_cloud_flow_state("env1", "flow1", {"state": "Started"})

    assert route.called
    assert flow.properties.get("state") == "Started"


def test_delete_cloud_flow(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.delete(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(204))

    client.delete_cloud_flow("env1", "flow1")

    assert route.called


def test_list_flow_actions(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/flowActions",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "actions": [
                    {"name": "action1", "type": "Type", "operationId": "op1"},
                    {"name": "action2", "type": "Type", "operationId": "op2"},
                ],
                "triggers": [{"name": "trigger1", "type": "Http"}],
            },
        ),
    )

    result = client.list_flow_actions("env1")

    assert route.called
    assert len(result.actions) == 2
    assert result.actions[0].operation_id == "op1"
    assert result.triggers[0].name == "trigger1"


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


def test_list_cloud_flow_runs_returns_header_token(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs",
        params={
            "api-version": "2022-03-01-preview",
            "status": "Succeeded",
            "$top": "5",
        },
    ).mock(
        return_value=httpx.Response(
            200,
            headers={"x-ms-continuation-token": "token123"},
            json={"value": [{"id": "run1", "name": "Run One", "status": "Succeeded"}]},
        )
    )

    page = client.list_cloud_flow_runs("env1", "flow1", status="Succeeded", top=5)

    assert route.called
    assert page.continuation_token == "token123"  # noqa: S105
    assert [run.id for run in page.runs] == ["run1"]


def test_list_cloud_flow_runs_uses_skiptoken(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs",
        params={
            "api-version": "2022-03-01-preview",
            "$skiptoken": "next-token",
        },
    ).mock(return_value=httpx.Response(200, json={"value": []}))

    client.list_cloud_flow_runs("env1", "flow1", continuation_token="next-token")  # noqa: S106

    assert route.called


def test_trigger_cloud_flow_run(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"triggerName": "manual", "inputs": {"foo": "bar"}}
    route = respx_mock.post(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(return_value=httpx.Response(202, json={"id": "run1", "status": "Running"}))

    run = client.trigger_cloud_flow_run("env1", "flow1", payload)

    assert route.called
    assert run.id == "run1"
    assert run.status == "Running"


def test_get_cloud_flow_run(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs/run1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"id": "run1", "status": "Succeeded"}))

    run = client.get_cloud_flow_run("env1", "flow1", "run1")

    assert run.id == "run1"
    assert run.status == "Succeeded"


def test_resubmit_cloud_flow_run(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs/run1",
        params={"api-version": "2022-03-01-preview"},
        json={"retryFailedActions": True},
    ).mock(return_value=httpx.Response(202, json={"id": "run2", "status": "Running"}))

    run = client.resubmit_cloud_flow_run("env1", "flow1", "run1", {"retryFailedActions": True})

    assert route.called
    assert run.id == "run2"


def test_delete_cloud_flow_run(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.delete(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs/run1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(204))

    client.delete_cloud_flow_run("env1", "flow1", "run1")

    assert route.called


def test_cancel_cloud_flow_run(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs/run1:cancel",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(202))

    client.cancel_cloud_flow_run("env1", "flow1", "run1")

    assert route.called


def test_get_cloud_flow_run_diagnostics(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env1/cloudFlows/flow1/runs/run1/diagnostics",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "runName": "run1",
                "issues": [
                    {
                        "actionName": "Action1",
                        "code": "ERR001",
                        "message": "Issue detected",
                    }
                ],
            },
        )
    )

    diagnostics = client.get_cloud_flow_run_diagnostics("env1", "flow1", "run1")

    assert route.called
    assert diagnostics.run_name == "run1"
    assert diagnostics.issues[0].code == "ERR001"


def test_restore_app_posts_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"restoreVersionId": "1.0"}
    route = respx_mock.post(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1:restore",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://api.powerplatform.com/operations/op1"},
            json={"status": "Accepted"},
        ),
    )

    handle = client.restore_app("env1", "app1", payload)

    assert route.called
    assert handle.operation_id == "op1"


def test_publish_app_posts_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"versionId": "2.0"}
    route = respx_mock.post(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1:publish",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202, headers={"Operation-Location": "https://api.powerplatform.com/operations/op2"}
        ),
    )

    handle = client.publish_app("env1", "app1", payload)

    assert route.called
    assert handle.operation_id == "op2"


def test_share_app_posts_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"principals": [{"id": "user", "principalType": "User", "roleName": "CanEdit"}]}
    route = respx_mock.post(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1:share",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202, headers={"Operation-Location": "https://api.powerplatform.com/operations/op3"}
        ),
    )

    handle = client.share_app("env1", "app1", payload)

    assert route.called
    assert handle.operation_id == "op3"


def test_revoke_app_share_posts_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"principalIds": ["user"]}
    route = respx_mock.post(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1:revokeShare",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202, headers={"Operation-Location": "https://api.powerplatform.com/operations/op4"}
        ),
    )

    handle = client.revoke_app_share("env1", "app1", payload)

    assert route.called
    assert handle.operation_id == "op4"


def test_set_app_owner_posts_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"owner": {"id": "user", "principalType": "User", "roleName": "CanEdit"}}
    route = respx_mock.post(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1:setOwner",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202, headers={"Operation-Location": "https://api.powerplatform.com/operations/op5"}
        ),
    )

    handle = client.set_app_owner("env1", "app1", payload)

    assert route.called
    assert handle.operation_id == "op5"


def test_list_app_permissions_parses_assignments(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/env1/apps/app1/permissions",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "assign1",
                        "roleName": "CanEdit",
                        "principalType": "User",
                        "displayName": "User One",
                    }
                ]
            },
        ),
    )

    assignments = client.list_app_permissions("env1", "app1")

    assert len(assignments) == 1
    assert assignments[0].role_name == "CanEdit"
    assert assignments[0].principal_type == "User"


def test_environment_copy_request_includes_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"targetEnvironmentId": "env2"}
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:copy",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/operations/op-copy"
            },
        )
    )

    handle = client.copy_environment("env1", payload)

    assert route.called
    request = route.calls[0].request
    assert request.url.path.endswith("/environmentmanagement/environments/env1:copy")
    assert handle.operation_location.endswith("op-copy")
    assert handle.metadata["status"] == "Accepted"


def test_environment_reset_request(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"resetType": "Minimal"}
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:reset",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202,
            json={},
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/operations/op-reset"
            },
        )
    )

    handle = client.reset_environment("env1", payload)

    assert route.called
    assert handle.operation_id == "op-reset"


def test_environment_backup_request(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"label": "manual"}
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:backup",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/operations/op-backup"
            },
        )
    )

    handle = client.backup_environment("env1", payload)

    assert route.called
    assert handle.operation_id == "op-backup"


def test_environment_restore_request(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"backupId": "backup-1"}
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1:restore",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/operations/op-restore"
            },
        )
    )

    handle = client.restore_environment("env1", payload)

    assert route.called
    assert handle.operation_id == "op-restore"


def test_list_environment_operations(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/operations",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"value": [{"name": "op"}]}))

    operations = client.list_environment_operations("env1")

    assert operations == [{"name": "op"}]


def test_get_operation(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/operations/op1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"status": "Running"}))

    status = client.get_operation("op1")

    assert status["status"] == "Running"


def test_wait_for_operation_polls_until_done(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/operations/op2"
    ).mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running"}),
            httpx.Response(200, json={"status": "Succeeded", "percentComplete": 100}),
        ]
    )

    status = client.wait_for_operation(
        "https://api.powerplatform.com/environmentmanagement/operations/op2",
        interval=0.0,
        timeout=5.0,
    )

    assert route.called
    assert len(route.calls) == 2
    assert status["status"].lower() == "succeeded"


def test_list_environment_groups(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"value": [{"id": "group1"}]}))

    groups = client.list_environment_groups()

    assert groups == [{"id": "group1"}]


def test_get_environment_group(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"id": "group1", "displayName": "Group"}))

    group = client.get_environment_group("group1")

    assert group["id"] == "group1"


def test_create_environment_group(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"displayName": "Group"}
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(return_value=httpx.Response(201, json={"id": "group1"}))

    group = client.create_environment_group(payload)

    assert route.called
    assert group["id"] == "group1"


def test_update_environment_group(respx_mock, token_getter):
    client = build_client(token_getter)
    payload = {"displayName": "Group"}
    route = respx_mock.patch(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1",
        params={"api-version": "2022-03-01-preview"},
        json=payload,
    ).mock(return_value=httpx.Response(200, json={"id": "group1", "displayName": "Group"}))

    group = client.update_environment_group("group1", payload)

    assert route.called
    assert group["displayName"] == "Group"


def test_delete_environment_group(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.delete(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1/operations/op3"
            },
        )
    )

    handle = client.delete_environment_group("group1")

    assert route.called
    assert handle.operation_id == "op3"


def test_apply_environment_group(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1/environments/env1/apply",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1/operations/apply-op"
            },
        )
    )

    handle = client.apply_environment_group("group1", "env1")

    assert route.called
    assert handle.operation_id == "apply-op"


def test_revoke_environment_group(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1/environments/env1/revoke",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1/operations/revoke-op"
            },
        )
    )

    handle = client.revoke_environment_group("group1", "env1")

    assert route.called
    assert handle.operation_id == "revoke-op"


def test_get_environment_group_operation(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environmentGroups/group1/operations/op1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"status": "Running"}))

    status = client.get_environment_group_operation("group1", "op1")

    assert status["status"] == "Running"


def test_enable_managed_environment(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/managedGovernance/enable",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/operations/enable-op"
            },
        )
    )

    handle = client.enable_managed_environment("env1")

    assert route.called
    assert handle.operation_id == "enable-op"


def test_disable_managed_environment(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/environmentmanagement/environments/env1/managedGovernance/disable",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={
                "Operation-Location": "https://api.powerplatform.com/environmentmanagement/operations/disable-op"
            },
        )
    )

    handle = client.disable_managed_environment("env1")

    assert route.called
    assert handle.operation_id == "disable-op"
