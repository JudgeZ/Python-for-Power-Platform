import importlib
import sys

import pytest

from pacx.clients.tenant_settings import TenantOperationResult
from pacx.models.tenant_settings import (
    TenantBooleanSetting,
    TenantFeatureControl,
    TenantFeatureControlList,
    TenantSettings,
)


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    for module_name in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module_name)
    module = importlib.import_module("pacx.cli")
    return module.app


class StubTenantSettingsClient:
    instances: list["StubTenantSettingsClient"] = []

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.update_calls: list[tuple[dict[str, object], bool]] = []
        self.feature_update_calls: list[tuple[str, dict[str, object], bool]] = []
        self.settings_access_calls: list[dict[str, object]] = []
        self.feature_access_calls: list[tuple[str, dict[str, object]]] = []
        self.get_calls = 0
        self.list_calls = 0
        StubTenantSettingsClient.instances.append(self)

    def get_settings(self) -> TenantSettings:
        self.get_calls += 1
        return TenantSettings(
            disable_community_sharing=TenantBooleanSetting(value=True)
        )

    def update_settings(self, payload: dict[str, object], *, prefer_async: bool = False) -> TenantOperationResult:
        self.update_calls.append((payload, prefer_async))
        return TenantOperationResult(resource=None, status_code=202 if prefer_async else 200, operation_location=None)

    def request_settings_access(self, payload: dict[str, object]) -> None:
        self.settings_access_calls.append(payload)

    def list_feature_controls(self) -> TenantFeatureControlList:
        self.list_calls += 1
        return TenantFeatureControlList(
            value=[TenantFeatureControl(name="FeatureA", value=True)],
            nextLink=None,
        )

    def update_feature_control(
        self, feature_name: str, payload: dict[str, object], *, prefer_async: bool = False
    ) -> TenantOperationResult:
        self.feature_update_calls.append((feature_name, payload, prefer_async))
        return TenantOperationResult(resource=None, status_code=202 if prefer_async else 200, operation_location=None)

    def request_feature_access(self, feature_name: str, payload: dict[str, object]) -> None:
        self.feature_access_calls.append((feature_name, payload))


@pytest.fixture
def tenant_cli(monkeypatch: pytest.MonkeyPatch):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.tenant.TenantSettingsClient", StubTenantSettingsClient)
    StubTenantSettingsClient.instances = []
    return app


def test_settings_get(cli_runner, tenant_cli) -> None:
    result = cli_runner.invoke(tenant_cli, ["tenant", "settings", "get"])
    assert result.exit_code == 0
    assert "disableCommunitySharing" in result.stdout
    assert StubTenantSettingsClient.instances[0].get_calls == 1


def test_settings_update_async(cli_runner, tenant_cli) -> None:
    result = cli_runner.invoke(
        tenant_cli,
        [
            "tenant",
            "settings",
            "update",
            "--payload",
            "{\"disableCommunitySharing\": {\"value\": false}}",
            "--async",
        ],
    )
    assert result.exit_code == 0
    client = StubTenantSettingsClient.instances[-1]
    assert client.update_calls == [({"disableCommunitySharing": {"value": False}}, True)]


def test_settings_request_access(cli_runner, tenant_cli) -> None:
    result = cli_runner.invoke(
        tenant_cli,
        [
            "tenant",
            "settings",
            "request-access",
            "--justification",
            "Need permissions",
            "--setting",
            "disableCommunitySharing",
        ],
    )
    assert result.exit_code == 0
    payload = StubTenantSettingsClient.instances[-1].settings_access_calls[-1]
    assert payload == {
        "justification": "Need permissions",
        "requestedSettings": ["disableCommunitySharing"],
    }


def test_feature_list(cli_runner, tenant_cli) -> None:
    result = cli_runner.invoke(tenant_cli, ["tenant", "feature", "list"])
    assert result.exit_code == 0
    assert "FeatureA" in result.stdout
    assert "status=enabled" in result.stdout
    assert StubTenantSettingsClient.instances[-1].list_calls == 1


def test_feature_update(cli_runner, tenant_cli) -> None:
    result = cli_runner.invoke(
        tenant_cli,
        [
            "tenant",
            "feature",
            "update",
            "FeatureA",
            "--payload",
            "{\"value\": true}",
            "--async",
        ],
    )
    assert result.exit_code == 0
    feature_call = StubTenantSettingsClient.instances[-1].feature_update_calls[-1]
    assert feature_call == ("FeatureA", {"value": True}, True)


def test_feature_request_access(cli_runner, tenant_cli) -> None:
    result = cli_runner.invoke(
        tenant_cli,
        [
            "tenant",
            "feature",
            "request-access",
            "FeatureA",
            "--justification",
            "Allow toggle",
        ],
    )
    assert result.exit_code == 0
    call = StubTenantSettingsClient.instances[-1].feature_access_calls[-1]
    assert call == ("FeatureA", {"justification": "Allow toggle"})
