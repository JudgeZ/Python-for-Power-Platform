
from __future__ import annotations

import httpx
import respx

from pacx.clients.connectors import ConnectorsClient


def test_list_apis(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis",
        params={"api-version": "2022-03-01-preview", "$top": 2},
    ).mock(return_value=httpx.Response(200, json={"value": [{"name": "conn1"}, {"name": "conn2"}]}))
    data = c.list_apis("ENV", top=2)
    assert len(data["value"]) == 2


def test_get_api(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"name": "myapi", "properties": {"displayName": "My API"}}))
    data = c.get_api("ENV", "myapi")
    assert data["name"] == "myapi"


def test_put_api_from_openapi(respx_mock, token_getter):
    c = ConnectorsClient(token_getter)
    respx_mock.put(
        "https://api.powerplatform.com/powerapps/environments/ENV/apis/myapi",
        params={"api-version": "2022-03-01-preview"},  # same string; params matching is lenient in respx
    ).mock(return_value=httpx.Response(200, json={"name": "myapi"}))
    data = c.put_api_from_openapi("ENV", "myapi", "openapi: 3.0.3\npaths: {}\n")
    assert data["name"] == "myapi"
