from __future__ import annotations

import httpx

from pacx.clients.power_pages_admin import PowerPagesAdminClient


def build_client(token_getter) -> PowerPagesAdminClient:
    return PowerPagesAdminClient(token_getter)


def test_start_and_stop_website(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    start_route = respx_mock.post(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/start",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"status": "Accepted"}))
    stop_route = respx_mock.post(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/stop",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"status": "Accepted"}))

    start_handle = client.start_website("env", "site")
    stop_handle = client.stop_website("env", "site")

    assert start_route.called
    assert stop_route.called
    assert start_handle.metadata["status"] == "Accepted"
    assert stop_handle.metadata["status"] == "Accepted"


def test_start_scans_capture_operation_location(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    quick_route = respx_mock.post(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/scan/quick/execute",
        params={"api-version": "2022-03-01-preview", "lcid": 1033},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Running"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/quick"},
        )
    )
    deep_route = respx_mock.post(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/scan/deep/start",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"status": "Running"},
            headers={"Operation-Location": "https://api.powerplatform.com/ops/deep"},
        )
    )

    quick_handle = client.start_quick_scan("env", "site", lcid=1033)
    deep_handle = client.start_deep_scan("env", "site")

    assert quick_route.called
    assert deep_route.called
    assert quick_handle.operation_location == "https://api.powerplatform.com/ops/quick"
    assert deep_handle.operation_id == "deep"


def test_wait_for_operation_polls_until_terminal(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.get("https://api.powerplatform.com/ops/quick").mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running", "percentComplete": 10}),
            httpx.Response(200, json={"status": "Succeeded"}),
        ]
    )

    final = client.wait_for_operation("https://api.powerplatform.com/ops/quick", interval=0.0, timeout=5.0)

    assert route.called
    assert final["status"].lower() == "succeeded"


def test_security_endpoints_return_payloads(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    score_route = respx_mock.get(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/scan/deep/getSecurityScore",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"score": 95}))
    report_route = respx_mock.get(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/scan/deep/getLatestCompletedReport",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"findings": []}))

    score = client.get_security_score("env", "site")
    report = client.get_security_report("env", "site")

    assert score_route.called
    assert report_route.called
    assert score == {"score": 95}
    assert report == {"findings": []}


def test_waf_operations(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    enable_route = respx_mock.post(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/enableWaf",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(202, headers={"Operation-Location": "https://api.powerplatform.com/ops/waf"}))
    disable_route = respx_mock.post(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/disableWaf",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={}))
    status_route = respx_mock.get(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/getWafStatus",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"enabled": True}))
    rules_put = respx_mock.put(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/createWafRules",
        params={"api-version": "2022-03-01-preview"},
        json={"rules": []},
    ).mock(return_value=httpx.Response(202, headers={"Operation-Location": "https://api.powerplatform.com/ops/rules"}))
    rules_get = respx_mock.get(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/getWafRules",
        params={"api-version": "2022-03-01-preview", "ruleType": "custom"},
    ).mock(return_value=httpx.Response(200, json={"rules": []}))

    enable_handle = client.enable_waf("env", "site")
    disable_handle = client.disable_waf("env", "site")
    status = client.get_waf_status("env", "site")
    rules_handle = client.create_waf_rules("env", "site", {"rules": []})
    rules = client.get_waf_rules("env", "site", rule_type="custom")

    assert enable_route.called
    assert disable_route.called
    assert status_route.called
    assert rules_put.called
    assert rules_get.called
    assert enable_handle.operation_location == "https://api.powerplatform.com/ops/waf"
    assert disable_handle.metadata == {}
    assert status == {"enabled": True}
    assert rules_handle.operation_id == "rules"
    assert rules == {"rules": []}


def test_update_site_visibility(respx_mock, token_getter) -> None:
    client = build_client(token_getter)
    route = respx_mock.patch(
        "https://api.powerplatform.com/powerpages/environments/env/websites/site/siteVisibility",
        params={"api-version": "2022-03-01-preview"},
        json={"visibility": "Private"},
    ).mock(return_value=httpx.Response(200, json={"visibility": "Private"}))

    result = client.update_site_visibility("env", "site", {"visibility": "Private"})

    assert route.called
    assert result == {"visibility": "Private"}
