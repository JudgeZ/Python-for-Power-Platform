from __future__ import annotations

import httpx

from pacx.clients.pva import DEFAULT_API_VERSION, PVAClient
from pacx.models.pva import (
    ChannelConfigurationPayload,
    ExportBotPackageRequest,
    ImportBotPackageRequest,
    PublishBotRequest,
    UnpublishBotRequest,
)


def build_client(token_getter):
    return PVAClient(token_getter)


def test_list_bots_with_top(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.get(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots",
        params={"api-version": DEFAULT_API_VERSION, "top": "5"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "bot-1",
                        "name": "Bot One",
                        "environmentId": "env",
                        "displayName": "Bot One",
                        "status": "Draft",
                    }
                ]
            },
        )
    )

    bots = client.list_bots("env", top=5)

    assert route.called
    assert len(bots) == 1
    assert bots[0].id == "bot-1"
    assert bots[0].display_name == "Bot One"


def test_get_bot(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "bot-1",
                "name": "Bot One",
                "environmentId": "env",
                "status": "Published",
            },
        )
    )

    bot = client.get_bot("env", "bot-1")

    assert bot.id == "bot-1"
    assert bot.status == "Published"


def test_publish_bot_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/publish",
        params={"api-version": DEFAULT_API_VERSION},
        json={"comment": "Ship it", "includedChannels": ["Teams"]},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/123"},
        )
    )

    request = PublishBotRequest(comment="Ship it", included_channels=["Teams"])
    handle = client.publish_bot("env", "bot-1", request)

    assert route.called
    assert handle.operation_location.endswith("/123")
    assert handle.metadata["status"] == "Accepted"


def test_unpublish_bot_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/unpublish",
        params={"api-version": DEFAULT_API_VERSION},
        json={"comment": "Staging", "channels": ["Web"]},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/456"},
        )
    )

    request = UnpublishBotRequest(comment="Staging", channels=["Web"])
    handle = client.unpublish_bot("env", "bot-1", request)

    assert route.called
    assert handle.operation_id == "456"


def test_export_bot_package_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/export",
        params={"api-version": DEFAULT_API_VERSION},
        json={
            "packageFormat": "application/zip",
            "includeAnalytics": True,
            "includeSecrets": False,
            "storageUrl": "https://storage/export.zip",
        },
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/export"},
        )
    )

    request = ExportBotPackageRequest(
        package_format="application/zip",
        include_analytics=True,
        include_secrets=False,
        storage_url="https://storage/export.zip",
    )
    handle = client.export_bot_package("env", "bot-1", request)

    assert route.called
    assert handle.operation_location.endswith("/export")


def test_import_bot_package_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/import",
        params={"api-version": DEFAULT_API_VERSION},
        json={
            "packageUrl": "https://storage/import.zip",
            "overwriteExistingResources": True,
            "publishOnCompletion": False,
            "localeMappings": {"en-US": "fr-FR"},
        },
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/import"},
        )
    )

    request = ImportBotPackageRequest(
        package_url="https://storage/import.zip",
        overwrite_existing_resources=True,
        publish_on_completion=False,
        locale_mappings={"en-US": "fr-FR"},
    )
    handle = client.import_bot_package("env", "bot-1", request)

    assert route.called
    assert handle.operation_id == "import"


def test_list_channels_returns_models(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/channels",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "chan-1",
                        "channelType": "WebChat",
                        "status": "Enabled",
                        "configuration": {"isEnabled": True},
                    }
                ]
            },
        )
    )

    channels = client.list_channels("env", "bot-1")

    assert channels[0].channel_type == "WebChat"
    assert channels[0].configuration["isEnabled"] is True


def test_create_channel_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/channels",
        params={"api-version": DEFAULT_API_VERSION},
        json={
            "channelType": "WebChat",
            "configuration": {"enabled": True},
            "isEnabled": True,
        },
    ).mock(
        return_value=httpx.Response(
            202,
            json={"id": "chan-1", "channelType": "WebChat"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/channel"},
        )
    )

    payload = ChannelConfigurationPayload(
        channel_type="WebChat",
        configuration={"enabled": True},
        is_enabled=True,
    )
    handle = client.create_channel("env", "bot-1", payload)

    assert route.called
    assert handle.metadata["id"] == "chan-1"


def test_update_channel_payload(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/channels/chan-1",
        params={"api-version": DEFAULT_API_VERSION},
        json={"channelType": "WebChat", "configuration": {"foo": "bar"}},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"id": "chan-1", "status": "Updating"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/channel-update"},
        )
    )

    payload = ChannelConfigurationPayload(channel_type="WebChat", configuration={"foo": "bar"})
    handle = client.update_channel("env", "bot-1", "chan-1", payload)

    assert route.called
    assert handle.metadata["status"] == "Updating"


def test_delete_channel_returns_operation_handle(respx_mock, token_getter):
    client = build_client(token_getter)
    route = respx_mock.delete(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/channels/chan-1",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/delete"},
        )
    )

    handle = client.delete_channel("env", "bot-1", "chan-1")

    assert route.called
    assert handle.operation_id == "delete"


def test_wait_for_operation_polls_until_done(respx_mock, token_getter):
    client = build_client(token_getter)
    operation_url = "https://api.powerplatform.com/ops/123"
    route = respx_mock.get(operation_url).mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running"}),
            httpx.Response(200, json={"status": "Succeeded", "result": "ok"}),
        ]
    )

    status = client.wait_for_operation(operation_url, interval=0.0)

    assert route.called
    assert status["status"].lower() == "succeeded"
    assert len(route.calls) == 2


def test_quarantine_operations(respx_mock, token_getter):
    client = build_client(token_getter)
    respx_mock.get(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/quarantine/status",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(return_value=httpx.Response(200, json={"state": "Active"}))

    set_route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/quarantine/set",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/quarantine-set"},
        )
    )

    unset_route = respx_mock.post(
        "https://api.powerplatform.com/powervirtualagents/environments/env/bots/bot-1/quarantine/unset",
        params={"api-version": DEFAULT_API_VERSION},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Accepted"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/quarantine-unset"},
        )
    )

    status = client.get_quarantine_status("env", "bot-1")
    set_handle = client.set_quarantined("env", "bot-1")
    unset_handle = client.set_unquarantined("env", "bot-1")

    assert status["state"] == "Active"
    assert set_route.called
    assert unset_route.called
    assert set_handle.operation_id == "quarantine-set"
    assert unset_handle.operation_id == "quarantine-unset"
