from __future__ import annotations

import importlib
import sys
from collections.abc import Iterable

import pytest

from pacx.clients.pva import DEFAULT_API_VERSION, OperationHandle
from pacx.models.pva import ChannelConfiguration


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    for name in [module for module in list(sys.modules) if module.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    return module.app, module


class StubPVAClient:
    instances: list[StubPVAClient] = []

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version or DEFAULT_API_VERSION
        self.create_calls: list[tuple[str, str, dict[str, object]]] = []
        self.update_calls: list[tuple[str, str, str, dict[str, object]]] = []
        self.delete_calls: list[tuple[str, str, str]] = []
        self.wait_calls: list[str] = []
        self.quarantine_set_calls: list[tuple[str, str]] = []
        self.quarantine_unset_calls: list[tuple[str, str]] = []
        self.quarantine_status_calls: list[tuple[str, str]] = []
        StubPVAClient.instances.append(self)

    def list_bots(self, environment_id: str, *, top: int | None = None) -> list[object]:
        return []

    def list_channels(self, environment_id: str, bot_id: str) -> Iterable[ChannelConfiguration]:
        self.list_channels_calls = getattr(self, "list_channels_calls", [])
        self.list_channels_calls.append((environment_id, bot_id))
        return [
            ChannelConfiguration(
                id="chan-1",
                channel_type="WebChat",
                status="Enabled",
                configuration={"isEnabled": True},
            )
        ]

    def get_channel(
        self, environment_id: str, bot_id: str, channel_id: str
    ) -> ChannelConfiguration:
        return ChannelConfiguration(
            id=channel_id,
            channel_type="WebChat",
            status="Enabled",
            configuration={"isEnabled": True},
        )

    def create_channel(
        self,
        environment_id: str,
        bot_id: str,
        payload,
    ) -> OperationHandle:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(by_alias=True, exclude_none=True)
        else:
            data = dict(payload)
        self.create_calls.append((environment_id, bot_id, data))
        return OperationHandle("https://example/operations/channel", {"status": "Accepted"})

    def update_channel(
        self,
        environment_id: str,
        bot_id: str,
        channel_id: str,
        payload,
    ) -> OperationHandle:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(by_alias=True, exclude_none=True)
        else:
            data = dict(payload)
        self.update_calls.append((environment_id, bot_id, channel_id, data))
        return OperationHandle("https://example/operations/channel", {"status": "Accepted"})

    def delete_channel(self, environment_id: str, bot_id: str, channel_id: str) -> OperationHandle:
        self.delete_calls.append((environment_id, bot_id, channel_id))
        return OperationHandle("https://example/operations/channel", {"status": "Accepted"})

    def wait_for_operation(
        self, operation_url: str, *, interval: float = 0.0, timeout: float = 0.0
    ):
        self.wait_calls.append(operation_url)
        return {"status": "succeeded"}

    def get_quarantine_status(self, environment_id: str, bot_id: str) -> dict[str, object]:
        self.quarantine_status_calls.append((environment_id, bot_id))
        return {"state": "Active"}

    def set_quarantined(self, environment_id: str, bot_id: str) -> OperationHandle:
        self.quarantine_set_calls.append((environment_id, bot_id))
        return OperationHandle("https://example/operations/quarantine", {"status": "Accepted"})

    def set_unquarantined(self, environment_id: str, bot_id: str) -> OperationHandle:
        self.quarantine_unset_calls.append((environment_id, bot_id))
        return OperationHandle("https://example/operations/quarantine", {"status": "Accepted"})


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli_app(monkeypatch)
    monkeypatch.setattr(module, "PVAClient", StubPVAClient)
    monkeypatch.setattr("pacx.cli.pva.PVAClient", StubPVAClient)
    monkeypatch.setattr(
        "pacx.cli.pva.resolve_environment_id_from_context",
        lambda ctx, value: value or "env-default",
    )
    StubPVAClient.instances = []
    return app, StubPVAClient


def test_enable_channel_polls_and_records_payload(cli_runner, cli_app) -> None:
    app, client_cls = cli_app
    result = cli_runner.invoke(
        app,
        [
            "pva",
            "bots",
            "channels",
            "enable",
            "--environment-id",
            "env-1",
            "--bot-id",
            "bot-1",
            "--channel-type",
            "WebChat",
            "--configuration",
            '{"greeting": "hi"}',
            "--enable",
            "--poll",
        ],
    )
    assert result.exit_code == 0, result.stdout
    client = client_cls.instances[-1]
    assert client.create_calls == [
        (
            "env-1",
            "bot-1",
            {"channelType": "WebChat", "configuration": {"greeting": "hi"}, "isEnabled": True},
        )
    ]
    assert client.wait_calls == ["https://example/operations/channel"]


def test_quarantine_status_and_set(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    status_result = cli_runner.invoke(
        app,
        [
            "pva",
            "bots",
            "quarantine",
            "status",
            "--environment-id",
            "env-1",
            "--bot-id",
            "bot-1",
        ],
    )
    assert status_result.exit_code == 0, status_result.stdout
    assert "Active" in status_result.stdout
    client = client_cls.instances[-1]
    assert client.quarantine_status_calls == [("env-1", "bot-1")]

    set_result = cli_runner.invoke(
        app,
        [
            "pva",
            "bots",
            "quarantine",
            "set",
            "--environment-id",
            "env-1",
            "--bot-id",
            "bot-1",
            "--poll",
        ],
    )
    assert set_result.exit_code == 0, set_result.stdout
    client = client_cls.instances[-1]
    assert client.quarantine_set_calls[-1] == ("env-1", "bot-1")
    assert client.wait_calls[-1] == "https://example/operations/quarantine"
