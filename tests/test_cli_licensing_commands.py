from __future__ import annotations

import importlib
import sys
from typing import Any

import pytest
import typer

from pacx.clients.licensing import DEFAULT_API_VERSION, LicensingOperation


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args: Any, **kwargs: Any):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for name in [module for module in sys.modules if module.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    return module.app, module


class StubLicensingClient:
    instances: list[StubLicensingClient] = []

    def __init__(self, token_getter, api_version: str = DEFAULT_API_VERSION) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.list_calls = 0
        self.refresh_calls: list[str] = []
        self.wait_calls: list[tuple[str, float, float]] = []
        self.currency_patch_calls: list[tuple[str, dict[str, Any]]] = []
        self.storage_calls = 0
        self.capacity_calls = 0
        StubLicensingClient.instances.append(self)

    def list_billing_policies(self) -> list[dict[str, Any]]:
        self.list_calls += 1
        return [{"id": "policy-1"}]

    def refresh_billing_policy_provisioning(self, policy_id: str) -> LicensingOperation:
        self.refresh_calls.append(policy_id)
        return LicensingOperation("https://example/operations/op-refresh", {"status": "Accepted"})

    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        self.wait_calls.append((operation_url, interval, timeout))
        return {"status": "Succeeded"}

    def patch_currency_allocation(
        self, environment_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.currency_patch_calls.append((environment_id, payload))
        return {"ok": True, **payload}

    def list_storage_warnings(self) -> list[dict[str, Any]]:
        self.storage_calls += 1
        return [{"category": "database"}]

    def get_tenant_capacity_details(self) -> dict[str, Any]:
        self.capacity_calls += 1
        return {"capacity": {"database": 10}}


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli_app(monkeypatch)
    monkeypatch.setattr(module, "LicensingClient", StubLicensingClient)
    monkeypatch.setattr("pacx.cli.licensing.LicensingClient", StubLicensingClient)
    StubLicensingClient.instances = []
    return app, StubLicensingClient


def test_billing_list_defaults_to_listing(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["licensing", "billing"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "policy-1" in result.stdout
    assert client_cls.instances[0].list_calls == 1


def test_refresh_provisioning_waits_when_requested(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["licensing", "billing", "refresh-provisioning", "policy-1", "--wait"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    client = client_cls.instances[-1]
    assert client.refresh_calls == ["policy-1"]
    assert client.wait_calls == [("https://example/operations/op-refresh", 2.0, 600.0)]
    assert "op-refresh" in result.stdout


def test_currency_patch_passes_payload(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        [
            "licensing",
            "allocations",
            "currency",
            "patch",
            "env-1",
            "--payload",
            '{"limit": 100}',
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    client = client_cls.instances[-1]
    assert client.currency_patch_calls == [("env-1", {"limit": 100})]


def test_storage_list_outputs_categories(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["licensing", "storage", "list"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "database" in result.stdout
    assert client_cls.instances[-1].storage_calls == 1


def test_capacity_tenant_prints_summary(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["licensing", "capacity", "tenant"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "database" in result.stdout
    assert client_cls.instances[-1].capacity_calls == 1
