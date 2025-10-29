from __future__ import annotations

from pacx.utils.operation_monitor import OperationMonitor


class StubResponse:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

    def json(self) -> dict[str, str]:
        return self._payload


class StubClient:
    def __init__(self, payloads: list[dict[str, str]]) -> None:
        self._payloads = payloads
        self.calls = 0

    def get(self, url: str) -> StubResponse:  # noqa: ARG002 - parity with HttpClient
        self.calls += 1
        index = min(self.calls - 1, len(self._payloads) - 1)
        return StubResponse(self._payloads[index])


def test_operation_monitor_stops_on_faulted_state(monkeypatch):
    monitor = OperationMonitor()
    client = StubClient([{"status": "Faulted"}])

    monkeypatch.setattr("pacx.utils.operation_monitor.time.sleep", lambda _: None)

    result = monitor.track(client, "https://example.test/operation")

    assert client.calls == 1
    assert result["status"] == "Faulted"


def test_operation_monitor_stops_on_error_state(monkeypatch):
    monitor = OperationMonitor()
    client = StubClient([{"state": "Error"}])

    monkeypatch.setattr("pacx.utils.operation_monitor.time.sleep", lambda _: None)

    result = monitor.track(client, "https://example.test/operation")

    assert client.calls == 1
    assert result["state"] == "Error"
