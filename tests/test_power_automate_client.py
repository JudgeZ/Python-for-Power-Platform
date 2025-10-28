from __future__ import annotations

import json

import httpx

from pacx.clients.power_automate import DEFAULT_API_VERSION, PowerAutomateClient


def build_client(token_getter):
    return PowerAutomateClient(token_getter)


def test_list_cloud_flows_returns_page(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env-1/cloudFlows",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "flow-1",
                        "name": "Flow One",
                        "properties": {"displayName": "Flow One"},
                    }
                ],
                "nextLink": "https://next",
            },
            headers={"x-ms-continuation-token": "token-123"},
        )
    )

    page = client.list_cloud_flows("env-1")

    assert route.called
    assert [flow.id for flow in page.flows] == ["flow-1"]
    assert page.next_link == "https://next"
    assert page.continuation_token == "token-123"  # noqa: S105


def test_get_cloud_flow_returns_model(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powerautomate/environments/env-1/cloudFlows/flow-1",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={"id": "flow-1", "properties": {"displayName": "Flow One"}},
        )
    )

    flow = client.get_cloud_flow("env-1", "flow-1")

    assert route.called
    assert flow.id == "flow-1"
    assert flow.properties["displayName"] == "Flow One"


def test_set_cloud_flow_state_submits_patch(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.patch(
        "https://api.powerplatform.com/powerautomate/environments/env-1/cloudFlows/flow-1",
        params={"api-version": DEFAULT_API_VERSION},
        json={"state": "Started"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={"id": "flow-1", "properties": {"state": "Started"}},
        )
    )

    flow = client.set_cloud_flow_state("env-1", "flow-1", "Started")

    assert route.called
    body = json.loads(route.calls[0].request.content.decode())
    assert body == {"state": "Started"}
    assert flow.properties["state"] == "Started"
