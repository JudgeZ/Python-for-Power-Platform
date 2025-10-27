from __future__ import annotations

import importlib
import json
import sys

import pytest
import typer

from pacx.clients.power_pages_admin import WebsiteOperationHandle


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


class StubAdminClient:
    def __init__(self, token_getter, *, api_version: str = "2022-03-01-preview") -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.calls: list[tuple[str, tuple, dict]] = []
        self.wait_calls: list[tuple[str, float, float]] = []

    def start_website(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        self.calls.append(("start", (environment_id, website_id), {}))
        return WebsiteOperationHandle("https://example/ops/start", {"status": "Running"})

    def stop_website(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        self.calls.append(("stop", (environment_id, website_id), {}))
        return WebsiteOperationHandle("https://example/ops/stop", {})

    def start_quick_scan(
        self, environment_id: str, website_id: str, *, lcid: int | None = None
    ) -> WebsiteOperationHandle:
        self.calls.append(("quick", (environment_id, website_id), {"lcid": lcid}))
        return WebsiteOperationHandle("https://example/ops/quick", {"status": "Running"})

    def start_deep_scan(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        self.calls.append(("deep", (environment_id, website_id), {}))
        return WebsiteOperationHandle("https://example/ops/deep", {})

    def enable_waf(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        self.calls.append(("waf-enable", (environment_id, website_id), {}))
        return WebsiteOperationHandle("https://example/ops/waf", {})

    def disable_waf(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        self.calls.append(("waf-disable", (environment_id, website_id), {}))
        return WebsiteOperationHandle("https://example/ops/waf-disable", {})

    def get_waf_status(self, environment_id: str, website_id: str) -> dict:
        self.calls.append(("waf-status", (environment_id, website_id), {}))
        return {"enabled": True}

    def create_waf_rules(self, environment_id: str, website_id: str, rules: dict) -> WebsiteOperationHandle:
        self.calls.append(("waf-rules", (environment_id, website_id), {"rules": rules}))
        return WebsiteOperationHandle("https://example/ops/rules", {})

    def get_waf_rules(self, environment_id: str, website_id: str, *, rule_type: str | None = None) -> dict:
        self.calls.append(("waf-rules-get", (environment_id, website_id), {"rule_type": rule_type}))
        return {"rules": ["rule"]}

    def update_site_visibility(self, environment_id: str, website_id: str, payload: dict) -> dict:
        self.calls.append(("visibility", (environment_id, website_id), {"payload": payload}))
        return payload

    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 900.0,
        on_update=None,
    ) -> dict:
        self.wait_calls.append((operation_url, interval, timeout))
        return {"status": "Succeeded"}


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesAdminClient", StubAdminClient)
    monkeypatch.setattr(
        "pacx.cli.pages.resolve_environment_id_from_context", lambda ctx, option_value: option_value or "env"
    )
    return app


def test_websites_start_waits_for_completion(cli_runner, cli_app):
    result = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "start",
            "--website-id",
            "site",
            "--environment-id",
            "env",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "Website start completed" in result.stdout
    assert "operation=start" in result.stdout


def test_websites_scan_modes(cli_runner, cli_app):
    result_quick = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "scan",
            "--website-id",
            "site",
            "--environment-id",
            "env",
            "--mode",
            "quick",
            "--lcid",
            "1033",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    result_deep = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "scan",
            "--website-id",
            "site",
            "--environment-id",
            "env",
            "--mode",
            "deep",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result_quick.exit_code == 0
    assert "Quick scan completed" in result_quick.stdout
    assert result_deep.exit_code == 0
    assert "Deep scan completed" in result_deep.stdout


def test_websites_waf_actions(cli_runner, cli_app):
    result_enable = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "waf",
            "--website-id",
            "site",
            "--environment-id",
            "env",
            "--action",
            "enable",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    result_status = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "waf",
            "--website-id",
            "site",
            "--environment-id",
            "env",
            "--action",
            "status",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    result_rules = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "waf",
            "--website-id",
            "site",
            "--environment-id",
            "env",
            "--action",
            "set-rules",
            "--rules",
            json.dumps({"rules": ["allow"]}),
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result_enable.exit_code == 0
    assert "WAF enable completed" in result_enable.stdout
    assert result_status.exit_code == 0
    assert "\"enabled\": true" in result_status.stdout.lower()
    assert result_rules.exit_code == 0
    assert "WAF rules update completed" in result_rules.stdout


def test_websites_visibility_updates(cli_runner, cli_app):
    result = cli_runner.invoke(
        cli_app,
        [
            "pages",
            "websites",
            "visibility",
            "--website-id",
            "site",
            "--environment-id",
            "env",
            "--payload",
            json.dumps({"visibility": "Private"}),
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "\"visibility\": " in result.stdout
