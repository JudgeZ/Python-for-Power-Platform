from __future__ import annotations

import importlib
import sys

import pytest
import typer

from pacx.clients.analytics import RecommendationOperationHandle
from pacx.models.analytics import (
    AdvisorAction,
    AdvisorActionResponse,
    AdvisorActionResult,
    AdvisorRecommendationAcknowledgement,
    AdvisorRecommendationActionResultSummary,
    AdvisorRecommendationDetail,
    AdvisorRecommendationOperationStatus,
    AdvisorRecommendationResource,
    AdvisorRecommendationStatus,
    AdvisorScenario,
)


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for name in [mod for mod in list(sys.modules) if mod.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    return module.app, module


class StubAnalyticsClient:
    instances: list[StubAnalyticsClient] = []

    def __init__(self, token_getter, *args, **kwargs):
        self.token = token_getter()
        self.list_scenarios_called = False
        self.list_actions_calls: list[str] = []
        self.iter_resource_calls: list[tuple[str, int | None]] = []
        self.list_recommendation_calls: list[str] = []
        self.show_calls: list[tuple[str, str]] = []
        self.status_calls: list[tuple[str, str]] = []
        self.ack_calls: list[tuple[str, str, object | None]] = []
        self.dismiss_calls: list[tuple[str, str, object | None]] = []
        self.wait_calls: list[tuple[RecommendationOperationHandle, float, float]] = []
        self.execute_calls: list[tuple[str, dict[str, object]]] = []
        StubAnalyticsClient.instances.append(self)

    def close(self) -> None:
        return None

    def __enter__(self) -> StubAnalyticsClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def list_scenarios(self):
        self.list_scenarios_called = True
        return [AdvisorScenario(scenario="maker", scenario_name="Maker Insights")]

    def list_actions(self, scenario: str):
        self.list_actions_calls.append(scenario)
        return [AdvisorAction(action_name="fix", display_name="Fix issue")]

    def iter_resources(self, scenario: str, top: int | None = None):
        self.iter_resource_calls.append((scenario, top))
        yield [
            AdvisorRecommendationResource(
                resource_id="res-1",
                resource_name="Resource One",
                resource_type="Environment",
                environment_id="env-1",
            )
        ]

    def list_recommendations(self, scenario: str):
        self.list_recommendation_calls.append(scenario)
        return [
            AdvisorRecommendationDetail(
                recommendation_id="rec-1",
                scenario=scenario,
                title="Check maker settings",
                severity="High",
            )
        ]

    def get_recommendation(self, scenario: str, recommendation_id: str):
        self.show_calls.append((scenario, recommendation_id))
        return AdvisorRecommendationDetail(
            recommendation_id=recommendation_id,
            scenario=scenario,
            title="Check maker settings",
            severity="High",
        )

    def get_recommendation_status(self, scenario: str, recommendation_id: str):
        self.status_calls.append((scenario, recommendation_id))
        return AdvisorRecommendationStatus(
            recommendation_id=recommendation_id,
            scenario=scenario,
            status="Acknowledged",
        )

    def acknowledge_recommendation(self, scenario: str, recommendation_id: str, payload):
        self.ack_calls.append((scenario, recommendation_id, payload))
        ack = AdvisorRecommendationAcknowledgement(
            recommendation_id=recommendation_id,
            scenario=scenario,
            operation_id="op-1",
            status="Accepted",
        )
        return RecommendationOperationHandle("https://example/operations/op-1", ack)

    def dismiss_recommendation(self, scenario: str, recommendation_id: str, payload):
        self.dismiss_calls.append((scenario, recommendation_id, payload))
        ack = AdvisorRecommendationAcknowledgement(
            recommendation_id=recommendation_id,
            scenario=scenario,
            operation_id="op-2",
            status="Accepted",
        )
        return RecommendationOperationHandle("https://example/operations/op-2", ack)

    def wait_for_operation(
        self,
        handle: RecommendationOperationHandle,
        *,
        interval: float = 2.0,
        timeout: float = 300.0,
    ):
        self.wait_calls.append((handle, interval, timeout))
        return AdvisorRecommendationOperationStatus(
            operation_id=handle.operation_id or "op-unknown",
            status="Succeeded",
            result_summary=AdvisorRecommendationActionResultSummary(outcome="Completed"),
        )

    def execute_action(self, action_name: str, payload):
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(by_alias=True)
        else:
            data = dict(payload)
        self.execute_calls.append((action_name, data))
        return AdvisorActionResponse(results=[AdvisorActionResult(action_final_result="Ok")])


@pytest.fixture
def analytics_cli_app(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli_app(monkeypatch)
    analytics_module = module.analytics
    monkeypatch.setattr(analytics_module, "AnalyticsClient", StubAnalyticsClient)
    StubAnalyticsClient.instances = []
    return app, StubAnalyticsClient


def test_cli_lists_scenarios(cli_runner, analytics_cli_app) -> None:
    app, client_cls = analytics_cli_app
    result = cli_runner.invoke(app, ["analytics", "scenarios"])
    assert result.exit_code == 0
    assert "Maker Insights" in result.stdout
    assert client_cls.instances[0].list_scenarios_called is True


def test_cli_acknowledge_waits_by_default(cli_runner, analytics_cli_app) -> None:
    app, client_cls = analytics_cli_app
    result = cli_runner.invoke(
        app,
        [
            "analytics",
            "acknowledge",
            "--scenario",
            "maker",
            "--recommendation-id",
            "rec-1",
        ],
    )
    assert result.exit_code == 0
    client = client_cls.instances[0]
    assert client.ack_calls == [("maker", "rec-1", None)]
    assert len(client.wait_calls) == 1
    assert "operation=op-1" in result.stdout


def test_cli_acknowledge_no_wait(cli_runner, analytics_cli_app) -> None:
    app, client_cls = analytics_cli_app
    result = cli_runner.invoke(
        app,
        [
            "analytics",
            "acknowledge",
            "--scenario",
            "maker",
            "--recommendation-id",
            "rec-1",
            "--no-wait",
        ],
    )
    assert result.exit_code == 0
    client = client_cls.instances[0]
    assert client.wait_calls == []


def test_cli_execute_action_serializes_parameters(cli_runner, analytics_cli_app) -> None:
    app, client_cls = analytics_cli_app
    result = cli_runner.invoke(
        app,
        [
            "analytics",
            "execute",
            "run",
            "--scenario",
            "maker",
            "--parameters",
            '{"force": true}',
        ],
    )
    assert result.exit_code == 0
    client = client_cls.instances[0]
    assert client.execute_calls == [
        ("run", {"scenario": "maker", "actionParameters": {"force": True}})
    ]
