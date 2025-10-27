import json

import httpx

from pacx.clients.policy import (
    DEFAULT_API_VERSION,
    DataLossPreventionClient,
    PolicyOperationHandle,
)
from pacx.models.policy import (
    ConnectorGroup,
    ConnectorReference,
    DataLossPreventionPolicy,
    PolicyAssignment,
)


def _make_policy_payload() -> dict[str, object]:
    return {
        "displayName": "Tenant Default",
        "state": "Active",
        "policyScope": "Tenant",
    }


def test_list_policies_returns_page(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "policy-1",
                        "displayName": "Policy One",
                        "state": "Active",
                        "policyScope": "Tenant",
                    },
                    {
                        "id": "policy-2",
                        "displayName": "Policy Two",
                        "state": "Draft",
                        "policyScope": "Environment",
                    },
                ],
                "nextLink": "https://example/policies?$skip=2",
            },
        )
    )

    page = client.list_policies()

    assert len(page.policies) == 2
    assert page.policies[0].display_name == "Policy One"
    assert page.next_link == "https://example/policies?$skip=2"


def test_get_policy_returns_model(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies/policy-1",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "policy-1",
                "displayName": "Policy One",
                "state": "Active",
                "policyScope": "Tenant",
            },
        )
    )

    policy = client.get_policy("policy-1")

    assert isinstance(policy, DataLossPreventionPolicy)
    assert policy.id == "policy-1"


def test_create_policy_returns_operation_handle(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    response = httpx.Response(
        202,
        json={"operationId": "op1", "status": "Running"},
        headers={"Operation-Location": "https://api.powerplatform.com/operations/op1"},
    )
    respx_mock.post(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies",
        params={"api-version": DEFAULT_API_VERSION},
        json=_make_policy_payload(),
    ).mock(return_value=response)

    payload = DataLossPreventionPolicy.model_validate(_make_policy_payload())
    handle = client.create_policy(payload)

    assert isinstance(handle, PolicyOperationHandle)
    assert handle.operation_location == "https://api.powerplatform.com/operations/op1"
    assert handle.operation_id == "op1"
    assert handle.operation is not None
    assert handle.operation.status == "Running"


def test_wait_for_operation_polls_until_succeeded(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    operation_url = "https://api.powerplatform.com/operations/op1"
    respx_mock.get(operation_url).mock(
        side_effect=[
            httpx.Response(200, json={"operationId": "op1", "status": "Running"}),
            httpx.Response(200, json={"operationId": "op1", "status": "Succeeded"}),
        ]
    )

    result = client.wait_for_operation(operation_url, interval=0.01, timeout=1.0)

    assert result.status == "Succeeded"


def test_update_connector_groups_serialises_models(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    groups = [
        ConnectorGroup(
            classification="Business",
            connectors=[ConnectorReference(id="shared-office365")],
        )
    ]
    called_payload: dict[str, object] = {}

    def capture(request):
        nonlocal called_payload
        called_payload = json.loads(request.content.decode())
        return httpx.Response(
            202,
            headers={"Operation-Location": "https://api.powerplatform.com/operations/op-update"},
            json={"operationId": "op-update", "status": "Running"},
        )

    respx_mock.patch(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies/policy-1/connectors",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(side_effect=capture)

    handle = client.update_connector_groups("policy-1", groups)

    assert called_payload == {
        "groups": [
            {
                "classification": "Business",
                "connectors": [
                    {"id": "shared-office365"},
                ],
            }
        ]
    }
    assert handle.operation_id == "op-update"


def test_list_assignments_returns_models(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies/policy-1/assignments",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "assignmentId": "assign-1",
                        "environmentId": "Default-123",
                        "assignmentType": "Include",
                    }
                ]
            },
        )
    )

    assignments = client.list_assignments("policy-1")

    assert len(assignments) == 1
    assert isinstance(assignments[0], PolicyAssignment)
    assert assignments[0].assignment_type == "Include"


def test_assign_policy_posts_assignments(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    assignments = [
        PolicyAssignment(environment_id="Default-123", assignment_type="Include"),
    ]

    received: dict[str, object] = {}

    def capture(request):
        nonlocal received
        received = json.loads(request.content.decode())
        return httpx.Response(
            202,
            json={"operationId": "assign-op", "status": "Running"},
            headers={"Operation-Location": "https://api.powerplatform.com/operations/assign-op"},
        )

    respx_mock.post(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies/policy-1/assignments",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(side_effect=capture)

    handle = client.assign_policy("policy-1", assignments)

    assert received == {
        "assignments": [
            {
                "assignmentType": "Include",
                "environmentId": "Default-123",
            }
        ]
    }
    assert handle.operation_id == "assign-op"


def test_remove_assignment_returns_handle(respx_mock, token_getter):
    client = DataLossPreventionClient(token_getter)
    respx_mock.delete(
        "https://api.powerplatform.com/policy/dataLossPreventionPolicies/policy-1/assignments/assign-1",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"operationId": "remove-op", "status": "Running"},
            headers={"Operation-Location": "https://api.powerplatform.com/operations/remove-op"},
        )
    )

    handle = client.remove_assignment("policy-1", "assign-1")

    assert handle.operation_id == "remove-op"
