from __future__ import annotations

from types import SimpleNamespace

from pacx.clients.analytics import (
    AnalyticsClient,
    RecommendationActionPayload,
    RecommendationOperationHandle,
)
from pacx.models.analytics import AdvisorActionRequest


class StubResponse:
    def __init__(self, json_data: dict | list | None = None, headers: dict | None = None):
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        return self._json

    @property
    def text(self) -> str:
        return "" if self._json is None else "payload"


def test_iter_resources_paginates(token_getter) -> None:
    client = AnalyticsClient(token_getter)

    responses = iter(
        [
            StubResponse(
                {
                    "value": [
                        {
                            "resourceId": "res-1",
                            "resourceName": "Resource One",
                            "resourceType": "Environment",
                        }
                    ],
                    "@odata.nextLink": "https://api.powerplatform.com/analytics/advisorRecommendations/maker/resources?$skiptoken=abc",
                }
            ),
            StubResponse({"value": [{"resourceId": "res-2"}]}),
        ]
    )
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, *, params: dict | None = None):
        calls.append((path, params or {}))
        return next(responses)

    client.http = SimpleNamespace(get=fake_get, close=lambda: None)

    batches = list(client.iter_resources("maker", top=1))

    assert calls == [
        (
            "analytics/advisorRecommendations/maker/resources",
            {"api-version": "2022-03-01-preview", "$top": 1},
        ),
        (
            "analytics/advisorRecommendations/maker/resources",
            {"api-version": "2022-03-01-preview", "$top": 1, "$skiptoken": "abc"},
        ),
    ]
    assert [[res.resource_id for res in page] for page in batches] == [["res-1"], ["res-2"]]


def test_wait_for_operation_uses_operation_location(token_getter) -> None:
    client = AnalyticsClient(token_getter)

    responses = iter(
        [
            StubResponse({"status": "Running"}),
            StubResponse(
                {
                    "operationId": "op-1",
                    "status": "Succeeded",
                    "resultSummary": {"outcome": "Completed"},
                }
            ),
        ]
    )
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, *, params: dict | None = None):
        calls.append((path, params))
        return next(responses)

    client.http = SimpleNamespace(get=fake_get, close=lambda: None)

    handle = RecommendationOperationHandle(
        "https://api.powerplatform.com/analytics/advisorRecommendations/operations/op-1",
        None,
    )
    status = client.wait_for_operation(handle, interval=0.0, timeout=1.0)

    assert calls == [
        (
            "https://api.powerplatform.com/analytics/advisorRecommendations/operations/op-1",
            {"api-version": "2022-03-01-preview"},
        ),
        (
            "https://api.powerplatform.com/analytics/advisorRecommendations/operations/op-1",
            {"api-version": "2022-03-01-preview"},
        ),
    ]
    assert status.operation_id == "op-1"


def test_acknowledge_payload_aliases(token_getter) -> None:
    client = AnalyticsClient(token_getter)
    captured: dict | None = None

    def fake_post(path: str, *, params: dict | None = None, json: dict | None = None):
        nonlocal captured
        captured = json
        return StubResponse(
            {
                "recommendationId": "rec-1",
                "scenario": "maker",
                "operationId": "op-1",
                "status": "Accepted",
            },
            headers={
                "Operation-Location": "https://api.powerplatform.com/analytics/advisorRecommendations/operations/op-1"
            },
        )

    client.http = SimpleNamespace(post=fake_post, close=lambda: None)

    handle = client.acknowledge_recommendation(
        "maker",
        "rec-1",
        RecommendationActionPayload(notes="note", requested_by="user"),
    )

    assert captured == {"notes": "note", "requestedBy": "user"}
    assert handle.operation_location is not None
    assert handle.operation_id == "op-1"


def test_execute_action_serializes_payload(token_getter) -> None:
    client = AnalyticsClient(token_getter)
    captured: dict | None = None

    def fake_post(path: str, *, params: dict | None = None, json: dict | None = None):
        nonlocal captured
        captured = json
        return StubResponse({"results": []})

    client.http = SimpleNamespace(post=fake_post, close=lambda: None)

    response = client.execute_action(
        "run",
        AdvisorActionRequest(scenario="maker", action_parameters={"force": True}),
    )

    assert captured == {"scenario": "maker", "actionParameters": {"force": True}}
    assert response.results == []
