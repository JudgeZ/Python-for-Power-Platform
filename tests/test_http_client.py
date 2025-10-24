from __future__ import annotations

from collections.abc import Iterable

import httpx
import pytest

from pacx.errors import HttpError
from pacx.http_client import HttpClient


class StubClient:
    def __init__(self, responses: Iterable[object]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        index = len(self.calls)
        response = self._responses[index]
        self.calls.append((method, url, kwargs))
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


def make_response(
    status: int,
    *,
    method: str = "GET",
    url: str = "https://example.test/endpoint",
    json: object | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)
    if json is not None:
        return httpx.Response(status, json=json, headers=headers, request=request)
    return httpx.Response(status, text=text, headers=headers, request=request)


def setup_client(monkeypatch: pytest.MonkeyPatch, responses: Iterable[object]) -> tuple[HttpClient, StubClient]:
    stub = StubClient(responses)
    monkeypatch.setattr("pacx.http_client.httpx.Client", lambda *_, **__: stub)
    client = HttpClient("https://example.test", token_getter=lambda: "token", default_headers={"X": "1"})
    return client, stub


def test_request_includes_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    response = make_response(200, json={"ok": True})
    client, stub = setup_client(monkeypatch, [response])

    result = client.get("/items", headers={"Y": "2"})

    assert result is response
    method, url, kwargs = stub.calls[0]
    assert method == "GET"
    assert url == "https://example.test/items"
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer token"
    assert headers["X"] == "1"
    assert headers["Y"] == "2"


def test_http_error_raises_with_details(monkeypatch: pytest.MonkeyPatch) -> None:
    error_response = make_response(404, json={"error": "missing"})
    client, _ = setup_client(monkeypatch, [error_response])

    with pytest.raises(HttpError) as exc_info:
        client.get("/missing")

    err = exc_info.value
    assert err.status_code == 404
    assert err.details == {"error": "missing"}


def test_retries_transport_and_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    transport_error = httpx.TransportError("boom")
    retry_response = make_response(503, headers={"Retry-After": "1"})
    success_response = make_response(200, json={"value": "ok"})
    sleep_calls: list[float] = []

    def record_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("pacx.http_client.time.sleep", record_sleep)
    client, stub = setup_client(monkeypatch, [transport_error, retry_response, success_response])

    result = client.get("/items")

    assert result is success_response
    assert len(stub.calls) == 3
    assert sleep_calls == [0.5, 1.0]


def test_client_close_closes_underlying(monkeypatch: pytest.MonkeyPatch) -> None:
    client, stub = setup_client(monkeypatch, [make_response(200)])

    client.close()

    assert stub.closed is True


def test_context_manager_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [make_response(200)]
    stub = StubClient(responses)
    monkeypatch.setattr("pacx.http_client.httpx.Client", lambda *_, **__: stub)

    with HttpClient("https://example.test", token_getter=lambda: "token") as client:
        client.get("/items")

    assert stub.closed is True
    assert stub.calls


def test_request_allows_absolute_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    client, stub = setup_client(monkeypatch, [make_response(200)])

    client.get("https://api.external.test/data")

    assert stub.calls[0][1] == "https://api.external.test/data"
