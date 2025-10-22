from __future__ import annotations
import httpx, respx
from pacx.clients.power_platform import PowerPlatformClient

def test_list_environments(respx_mock, token_getter):
    client = PowerPlatformClient(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/environmentmanagement/environments",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"value": [{"id": "env1", "environmentType": "Sandbox", "location": "US"}]}))
    envs = client.list_environments()
    assert route.called
    assert len(envs) == 1
    assert envs[0].id == "env1"
