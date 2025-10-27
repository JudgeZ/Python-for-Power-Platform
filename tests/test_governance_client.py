from __future__ import annotations

import httpx

from pacx.clients.governance import GovernanceClient


def test_create_cross_tenant_report_returns_operation(respx_mock, token_getter) -> None:
    route = respx_mock.post(
        "https://api.powerplatform.com/governance/crossTenantConnectionReports"
    ).mock(
        return_value=httpx.Response(
            202,
            json={"id": "report-123", "status": "Running"},
            headers={
                "Operation-Location": "https://api.powerplatform.com/governance/crossTenantConnectionReports/report-123"
            },
        )
    )
    client = GovernanceClient(token_getter)

    handle = client.create_cross_tenant_connection_report({"scope": "AllTenants"})

    assert route.called
    assert handle.operation_location.endswith("/report-123")
    assert handle.metadata["id"] == "report-123"
    assert handle.resource_id == "report-123"


def test_wait_for_report_polls_until_complete(respx_mock, token_getter) -> None:
    statuses = [
        httpx.Response(200, json={"status": "Running"}),
        httpx.Response(200, json={"status": "Completed", "data": [1]}),
    ]
    route = respx_mock.get(
        "https://api.powerplatform.com/governance/crossTenantConnectionReports/report-123"
    ).mock(side_effect=statuses)
    client = GovernanceClient(token_getter)

    result = client.wait_for_report("report-123", interval=0, timeout=1)

    assert route.call_count == 2
    assert result["status"] == "Completed"


def test_list_rule_assignments_includes_filters(respx_mock, token_getter) -> None:
    route = respx_mock.get(
        "https://api.powerplatform.com/governance/ruleBasedPolicies/assignments"
    ).mock(return_value=httpx.Response(200, json={"value": []}))
    client = GovernanceClient(token_getter)

    client.list_rule_assignments(environment_id="env-1", policy_id="policy-1")

    assert route.called
    params = route.calls[0].request.url.params
    assert params["environmentId"] == "env-1"
    assert params["policyId"] == "policy-1"
    assert "environmentGroupId" not in params
