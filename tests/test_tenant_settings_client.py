import json

import httpx

from pacx.clients.tenant_settings import TenantSettingsClient
from pacx.models.tenant_settings import (
    TenantBooleanSettingUpdate,
    TenantFeatureControlPatch,
    TenantSettingsPatch,
)


def test_update_settings_payload(token_getter, respx_mock) -> None:
    route = respx_mock.patch("https://api.powerplatform.com/tenantsettings").mock(
        return_value=httpx.Response(
            200,
            json={"disableCommunitySharing": {"value": True}},
        )
    )
    client = TenantSettingsClient(token_getter)
    patch = TenantSettingsPatch(
        disableCommunitySharing=TenantBooleanSettingUpdate(
            value=True, justification="Compliance requirement"
        )
    )

    result = client.update_settings(patch)

    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent == {
        "disableCommunitySharing": {
            "value": True,
            "justification": "Compliance requirement",
        }
    }
    assert result.resource is not None
    assert result.resource.disable_community_sharing is not None
    assert result.resource.disable_community_sharing.value is True


def test_request_settings_access(token_getter, respx_mock) -> None:
    route = respx_mock.post("https://api.powerplatform.com/tenantsettings/requestAccess").mock(
        return_value=httpx.Response(202)
    )
    client = TenantSettingsClient(token_getter)

    client.request_settings_access(
        {
            "justification": "Need to unblock change",
            "requestedSettings": ["disableCommunitySharing"],
        }
    )

    assert route.called
    body = json.loads(route.calls[0].request.content)
    assert body == {
        "justification": "Need to unblock change",
        "requestedSettings": ["disableCommunitySharing"],
    }


def test_update_feature_control_payload(token_getter, respx_mock) -> None:
    route = respx_mock.patch(
        "https://api.powerplatform.com/tenantsettings/featureControl/ExperimentalFeature"
    ).mock(
        return_value=httpx.Response(
            202, headers={"Operation-Location": "https://api.example/ops/123"}
        )
    )
    client = TenantSettingsClient(token_getter)

    patch = TenantFeatureControlPatch(value=True, justification="Pilot rollout")
    result = client.update_feature_control("ExperimentalFeature", patch, prefer_async=True)

    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"value": True, "justification": "Pilot rollout"}
    assert route.calls[0].request.headers.get("Prefer") == "respond-async"
    assert result.accepted is True
    assert result.operation_location == "https://api.example/ops/123"


def test_request_feature_access(token_getter, respx_mock) -> None:
    route = respx_mock.post(
        "https://api.powerplatform.com/tenantsettings/featureControl/ExperimentalFeature/requestAccess"
    ).mock(return_value=httpx.Response(202))
    client = TenantSettingsClient(token_getter)

    client.request_feature_access("ExperimentalFeature", {"justification": "Needed for launch"})

    assert route.called
    payload = json.loads(route.calls[0].request.content)
    assert payload == {"justification": "Needed for launch"}
