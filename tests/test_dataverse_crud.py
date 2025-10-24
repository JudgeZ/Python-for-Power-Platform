from __future__ import annotations

import httpx

from pacx.clients.dataverse import DataverseClient


def test_whoami(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/WhoAmI()").mock(
        return_value=httpx.Response(200, json={"UserId": "00000000-0000-0000-0000-000000000001"})
    )
    data = dv.whoami()
    assert data["UserId"].endswith("1")


def test_crud_cycle(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")

    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/accounts", params={"$select": "name"}
    ).mock(return_value=httpx.Response(200, json={"value": [{"name": "a"}]}))
    assert dv.list_records("accounts", select="name")["value"][0]["name"] == "a"

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/accounts").mock(
        return_value=httpx.Response(
            201, headers={"OData-EntityId": "https://example/.../accounts(12345)"}
        )
    )
    created = dv.create_record("accounts", {"name": "test"})
    assert "entityUrl" in created

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/accounts(12345)").mock(
        return_value=httpx.Response(200, json={"name": "test"})
    )
    assert dv.get_record("accounts", "12345")["name"] == "test"

    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/accounts(12345)").mock(
        return_value=httpx.Response(204)
    )
    dv.update_record("accounts", "12345", {"name": "updated"})

    respx_mock.delete("https://example.crm.dynamics.com/api/data/v9.2/accounts(12345)").mock(
        return_value=httpx.Response(204)
    )
    dv.delete_record("accounts", "12345")
