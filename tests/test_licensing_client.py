from __future__ import annotations

import json

import httpx

from pacx.clients.licensing import DEFAULT_API_VERSION, LicensingClient


def build_client(token_getter):
    return LicensingClient(token_getter)


def test_create_billing_policy(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    payload = {"displayName": "Finance"}
    route = respx_mock.post(
        "https://api.powerplatform.com/licensing/billingPolicies",
        params={"api-version": DEFAULT_API_VERSION},
        json=payload,
    ).mock(return_value=httpx.Response(201, json={"id": "bp1"}))

    result = client.create_billing_policy(payload)

    assert route.called
    assert result["id"] == "bp1"


def test_refresh_billing_policy_provisioning(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/licensing/billingPolicies/policy1:refreshProvisioningStatus",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            202,
            headers={"Operation-Location": "https://api.powerplatform.com/licensing/operations/op123"},
            json={"status": "Accepted"},
        )
    )

    handle = client.refresh_billing_policy_provisioning("policy1")

    assert route.called
    assert handle.operation_id == "op123"
    assert handle.metadata["status"] == "Accepted"


def test_wait_for_operation_polls_until_complete(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    operation_url = "https://api.powerplatform.com/licensing/operations/op123"
    respx_mock.get(operation_url).mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running"}),
            httpx.Response(200, json={"status": "Succeeded", "result": {"value": 1}}),
        ]
    )

    final = client.wait_for_operation(operation_url, interval=0.01, timeout=1.0)

    assert final["status"].lower() == "succeeded"
    assert final["result"] == {"value": 1}


def test_patch_currency_allocation_sends_payload(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    payload = {"allocation": {"capacity": 10}}
    route = respx_mock.patch(
        "https://api.powerplatform.com/licensing/environments/env1/currencyAllocation",
        params={"api-version": DEFAULT_API_VERSION},
        json=payload,
    ).mock(return_value=httpx.Response(200, json=payload))

    result = client.patch_currency_allocation("env1", payload)

    assert route.called
    body = json.loads(route.calls[0].request.content.decode())
    assert body == payload
    assert result == payload


def test_update_environment_allocations_sends_payload(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    payload = {"database": 5}
    route = respx_mock.patch(
        "https://api.powerplatform.com/licensing/environments/env1/allocations",
        params={"api-version": DEFAULT_API_VERSION},
        json=payload,
    ).mock(return_value=httpx.Response(200, json=payload))

    result = client.update_environment_allocations("env1", payload)

    assert route.called
    body = json.loads(route.calls[0].request.content.decode())
    assert body == payload
    assert result == payload


def test_list_currency_reports_handles_single_object(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/licensing/currencyReports",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(return_value=httpx.Response(200, json={"id": "report1"}))

    reports = client.list_currency_reports()

    assert reports == [{"id": "report1"}]
