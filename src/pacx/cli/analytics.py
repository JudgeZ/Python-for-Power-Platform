from __future__ import annotations

import json
from typing import Any, cast

import typer

from ..clients.analytics import (
    AnalyticsClient,
    RecommendationOperationHandle,
)
from ..models.analytics import AdvisorActionRequest, RecommendationActionPayload
from .common import console, get_token_getter, handle_cli_errors

app = typer.Typer(help="Explore Advisor Recommendations analytics APIs.")


def _build_client(ctx: typer.Context) -> AnalyticsClient:
    token_getter = get_token_getter(ctx)
    return AnalyticsClient(token_getter)


def _print_operation(message: str, handle: RecommendationOperationHandle) -> None:
    operation_id = handle.operation_id or "?"
    location = handle.operation_location
    if location:
        console.print(f"[green]{message}[/green] operation={operation_id} location={location}")
    else:
        console.print(f"[green]{message}[/green] operation={operation_id}")
    if handle.acknowledgement:
        ack = handle.acknowledgement
        console.print(
            f"status={ack.status} acknowledgedBy={ack.acknowledged_by or 'n/a'} "
            f"message={ack.message or ''}"
        )


def _parse_parameters(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        payload = json.loads(cast(str, raw))
    except json.JSONDecodeError as exc:  # pragma: no cover - validation handled by Typer
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Parameters must be a JSON object.")
    return payload


@app.command("scenarios")
@handle_cli_errors
def list_scenarios(ctx: typer.Context) -> None:
    """List available recommendation scenarios."""

    with _build_client(ctx) as client:
        scenarios = client.list_scenarios()
    if not scenarios:
        console.print("No scenarios found.")
        return
    for scenario in scenarios:
        label = scenario.scenario_name or scenario.scenario or "(unknown)"
        console.print(f"[bold]{label}[/bold] id={scenario.scenario}")


@app.command("actions")
@handle_cli_errors
def list_actions(
    ctx: typer.Context,
    scenario: str = typer.Argument(..., help="Scenario identifier"),
) -> None:
    """List actions available for a scenario."""

    with _build_client(ctx) as client:
        actions = client.list_actions(scenario)
    if not actions:
        console.print("No actions found.")
        return
    for action in actions:
        console.print(
            f"[bold]{action.display_name or action.action_name}[/bold] name={action.action_name}"
        )


@app.command("resources")
@handle_cli_errors
def list_resources(
    ctx: typer.Context,
    scenario: str = typer.Argument(..., help="Scenario identifier"),
    top: int | None = typer.Option(None, "--top", help="Page size to request."),
    pages: int = typer.Option(1, "--pages", help="Number of pages to fetch (0 for all)."),
) -> None:
    """Browse impacted resources for a recommendation scenario."""

    with _build_client(ctx) as client:
        fetched = 0
        for page in client.iter_resources(scenario, top=top):
            fetched += 1
            for resource in page:
                console.print(
                    "[bold]{name}[/bold] id={rid} type={rtype} env={env}".format(
                        name=resource.resource_name or resource.resource_id or "(unknown)",
                        rid=resource.resource_id or "?",
                        rtype=resource.resource_type or "?",
                        env=resource.environment_id or "?",
                    )
                )
            if pages and fetched >= pages:
                break


@app.command("recommendations")
@handle_cli_errors
def list_recommendations(
    ctx: typer.Context,
    scenario: str = typer.Argument(..., help="Scenario identifier"),
) -> None:
    """List recommendations for a scenario."""

    with _build_client(ctx) as client:
        items = client.list_recommendations(scenario)
    if not items:
        console.print("No recommendations available.")
        return
    for rec in items:
        console.print(
            f"[bold]{rec.title}[/bold] id={rec.recommendation_id} severity={rec.severity} status={rec.status}"
        )


@app.command("show")
@handle_cli_errors
def show_recommendation(
    ctx: typer.Context,
    scenario: str = typer.Argument(..., help="Scenario identifier"),
    recommendation_id: str = typer.Argument(..., help="Recommendation identifier"),
) -> None:
    """Display a single recommendation in detail."""

    with _build_client(ctx) as client:
        rec = client.get_recommendation(scenario, recommendation_id)
    console.print_json(data=rec.model_dump(mode="json", by_alias=True))


@app.command("status")
@handle_cli_errors
def recommendation_status(
    ctx: typer.Context,
    scenario: str = typer.Argument(..., help="Scenario identifier"),
    recommendation_id: str = typer.Argument(..., help="Recommendation identifier"),
) -> None:
    """Fetch the lifecycle status for a recommendation."""

    with _build_client(ctx) as client:
        status = client.get_recommendation_status(scenario, recommendation_id)
    console.print_json(data=status.model_dump(mode="json", by_alias=True))


def _action_payload(
    notes: str | None, requested_by: str | None
) -> RecommendationActionPayload | None:
    payload = RecommendationActionPayload(notes=notes, requestedBy=requested_by)
    return payload if payload.to_payload() else None


def _handle_async(
    client: AnalyticsClient,
    handle: RecommendationOperationHandle,
    *,
    wait: bool,
    interval: float,
    timeout: float,
) -> None:
    _print_operation("Operation accepted", handle)
    if not wait:
        return
    status = client.wait_for_operation(handle, interval=interval, timeout=timeout)
    console.print_json(data=status.model_dump(mode="json", by_alias=True))


@app.command("acknowledge")
@handle_cli_errors
def acknowledge_recommendation(
    ctx: typer.Context,
    scenario: str = typer.Option(..., "--scenario", "-s", help="Scenario identifier"),
    recommendation_id: str = typer.Option(
        ..., "--recommendation-id", "-r", help="Recommendation identifier"
    ),
    notes: str | None = typer.Option(None, help="Optional remediation notes."),
    requested_by: str | None = typer.Option(None, help="User acknowledging the recommendation."),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for asynchronous completion."),
    interval: float = typer.Option(2.0, help="Polling interval in seconds."),
    timeout: float = typer.Option(300.0, help="Polling timeout in seconds."),
) -> None:
    """Acknowledge a recommendation."""

    payload = _action_payload(notes, requested_by)
    with _build_client(ctx) as client:
        handle = client.acknowledge_recommendation(scenario, recommendation_id, payload)
        _handle_async(client, handle, wait=wait, interval=interval, timeout=timeout)


@app.command("dismiss")
@handle_cli_errors
def dismiss_recommendation(
    ctx: typer.Context,
    scenario: str = typer.Option(..., "--scenario", "-s", help="Scenario identifier"),
    recommendation_id: str = typer.Option(
        ..., "--recommendation-id", "-r", help="Recommendation identifier"
    ),
    notes: str | None = typer.Option(None, help="Optional dismissal notes."),
    requested_by: str | None = typer.Option(None, help="User dismissing the recommendation."),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for asynchronous completion."),
    interval: float = typer.Option(2.0, help="Polling interval in seconds."),
    timeout: float = typer.Option(300.0, help="Polling timeout in seconds."),
) -> None:
    """Dismiss a recommendation."""

    payload = _action_payload(notes, requested_by)
    with _build_client(ctx) as client:
        handle = client.dismiss_recommendation(scenario, recommendation_id, payload)
        _handle_async(client, handle, wait=wait, interval=interval, timeout=timeout)


@app.command("execute")
@handle_cli_errors
def execute_action(
    ctx: typer.Context,
    action_name: str = typer.Argument(..., help="Action to execute."),
    scenario: str = typer.Option(..., "--scenario", "-s", help="Scenario identifier"),
    parameters: str | None = typer.Option(
        None, "--parameters", help="JSON object of action parameters."
    ),
) -> None:
    """Execute an advisor action for a scenario."""

    action_parameters = _parse_parameters(parameters)
    request = AdvisorActionRequest(scenario=scenario, actionParameters=action_parameters)
    with _build_client(ctx) as client:
        response = client.execute_action(action_name, request)
    console.print_json(data=response.model_dump(mode="json", by_alias=True))


__all__ = ["app"]
