from __future__ import annotations

import httpx

from pacx.http_client import HttpClient


def test_retries_on_429(respx_mock):
    client = HttpClient("https://example.com", token_getter=lambda: "t", max_retries=2)
    calls = {"n": 0}

    @respx_mock.route(method="GET", url="https://example.com/resource")
    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    resp = client.get("resource")
    assert resp.status_code == 200
    assert calls["n"] == 3
