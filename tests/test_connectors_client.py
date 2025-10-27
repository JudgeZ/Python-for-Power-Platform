from __future__ import annotations

import httpx
import pytest

from pacx.clients.connectors import ConnectorsClient
from pacx.errors import HttpError


def test_list_apis(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis",
        params={"api-version": "2022-03-01-preview", "$top": 2},
    ).mock(return_value=httpx.Response(200, json={"value": [{"name": "conn1"}, {"name": "conn2"}]}))
    data = c.list_apis("ENV", top=2)
    assert len(data["value"]) == 2


def test_iter_apis_follows_pagination(respx_mock, token_getter):
    client = ConnectorsClient(token_getter)

    first_page = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis",
        params={"api-version": "2022-03-01-preview", "$top": 1},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [{"name": "first"}],
                "@odata.nextLink": "https://api.powerplatform.com/powerapps/environments/ENV/apis?$skiptoken=abc",
            },
        )
    )

    second_page = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis",
        params={"api-version": "2022-03-01-preview", "$skiptoken": "abc"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [{"name": "second"}],
                "@odata.nextLink": "https://api.powerplatform.com/powerapps/environments/ENV/apis?$skiptoken=def",
            },
        )
    )

    third_page = respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis",
        params={"api-version": "2022-03-01-preview", "$skiptoken": "def"},
    ).mock(return_value=httpx.Response(200, json={"value": [{"name": "third"}]}))

    pages = list(client.iter_apis("ENV", top=1))

    assert [item["name"] for page in pages for item in page] == [
        "first",
        "second",
        "third",
    ]
    assert first_page.called
    assert second_page.called
    assert third_page.called


def test_get_api(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200, json={"name": "myapi", "properties": {"displayName": "My API"}}
        )
    )
    data = c.get_api("ENV", "myapi")
    assert data["name"] == "myapi"


def test_put_api_from_openapi(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.put(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={
            "api-version": "2022-03-01-preview"
        },  # same string; params matching is lenient in respx
    ).mock(return_value=httpx.Response(200, json={"name": "myapi"}))
    data = c.put_api_from_openapi("ENV", "myapi", "openapi: 3.0.3\npaths: {}\n")
    assert data["name"] == "myapi"


def test_delete_api_success(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.delete(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(204))

    assert c.delete_api("ENV", "myapi") is True


def test_delete_api_raises_for_missing(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.delete(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/missing",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(404, json={"error": "not found"}))

    with pytest.raises(HttpError):
        c.delete_api("ENV", "missing")


def test_list_apis_connectivity_routes(respx_mock, token_getter):
    client = ConnectorsClient(token_getter, use_connectivity=True, client_request_id="stub-request")
    route = respx_mock.get(
        "https://api.powerplatform.com/connectivity/environments/ENV/customConnectors",
        params={"api-version": "2022-03-01-preview", "$top": 3},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(200, json={"value": []}))

    payload = client.list_apis("ENV", top=3)

    assert payload["value"] == []
    assert route.called


def test_put_api_uses_connectivity_upsert(respx_mock, token_getter):
    client = ConnectorsClient(token_getter, use_connectivity=True, client_request_id="stub-request")
    update_route = respx_mock.patch(
        "https://api.powerplatform.com/connectivity/environments/ENV/customConnectors/sample",
        params={"api-version": "2022-03-01-preview"},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(404, json={"error": "NotFound"}))
    create_route = respx_mock.post(
        "https://api.powerplatform.com/connectivity/environments/ENV/customConnectors",
        params={"api-version": "2022-03-01-preview"},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(201, json={"name": "sample"}))

    payload = {"properties": {"displayName": "Sample"}}
    result = client.put_api("ENV", "sample", payload)

    assert result["name"] == "sample"
    assert update_route.called
    assert create_route.called


def test_validate_custom_connector_route(respx_mock, token_getter):
    client = ConnectorsClient(token_getter, use_connectivity=True, client_request_id="stub-request")
    route = respx_mock.post(
        "https://api.powerplatform.com/connectivity/environments/ENV/customConnectors/sample:validate",
        params={"api-version": "2022-03-01-preview"},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(200, json={"status": "Succeeded"}))

    response = client.validate_custom_connector(
        "ENV", "sample", {"properties": {"displayName": "Sample"}}
    )

    assert response["status"] == "Succeeded"
    assert route.called


def test_runtime_status_route(respx_mock, token_getter):
    client = ConnectorsClient(token_getter, use_connectivity=True, client_request_id="stub-request")
    route = respx_mock.get(
        "https://api.powerplatform.com/connectivity/environments/ENV/customConnectors/sample/runtimeStatus",
        params={"api-version": "2022-03-01-preview"},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(200, json={"availabilityState": "Healthy"}))

    payload = client.get_custom_connector_runtime_status("ENV", "sample")

    assert payload["availabilityState"] == "Healthy"
    assert route.called


def test_policy_template_route(respx_mock, token_getter):
    client = ConnectorsClient(token_getter, use_connectivity=True, client_request_id="stub-request")
    list_route = respx_mock.get(
        "https://api.powerplatform.com/connectivity/policyTemplates",
        params={"api-version": "2022-03-01-preview"},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(200, json={"value": []}))
    get_route = respx_mock.get(
        "https://api.powerplatform.com/connectivity/policyTemplates/template-1",
        params={"api-version": "2022-03-01-preview"},
        headers={"x-ms-client-request-id": "stub-request"},
    ).mock(return_value=httpx.Response(200, json={"name": "template-1"}))

    templates = client.list_policy_templates()
    template = client.get_policy_template("template-1")

    assert templates["value"] == []
    assert template["name"] == "template-1"
    assert list_route.called
    assert get_route.called
