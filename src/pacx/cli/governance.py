"""Typer commands for Power Platform governance APIs."""

from __future__ import annotations

import json
from typing import Any, cast

import typer
from rich import print

from ..clients.governance import (
    DEFAULT_API_VERSION,
    GovernanceClient,
    GovernanceOperation,
)
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Governance APIs")
report_app = typer.Typer(help="Cross-tenant connection reports")
policy_app = typer.Typer(help="Rule-based governance policies")
assignment_app = typer.Typer(help="Rule-based policy assignments")

app.add_typer(report_app, name="report")
app.add_typer(policy_app, name="policy")
app.add_typer(assignment_app, name="assignment")


def _state(ctx: typer.Context) -> dict[str, Any]:
    return ctx.ensure_object(dict)


def _current_version(ctx: typer.Context) -> str:
    state = _state(ctx)
    version = state.get("governance_api_version", DEFAULT_API_VERSION)
    if isinstance(version, str) and version:
        return version
    return DEFAULT_API_VERSION


def _build_client(ctx: typer.Context) -> GovernanceClient:
    token_getter = get_token_getter(ctx)
    return GovernanceClient(token_getter, api_version=_current_version(ctx))


def _parse_payload(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    raw_str = cast(str, raw)
    try:
        payload = json.loads(raw_str)
    except json.JSONDecodeError as exc:  # pragma: no cover - validation path
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return payload


def _print_operation(message: str, handle: GovernanceOperation) -> None:
    if handle.operation_location:
        print(f"[green]{message} accepted[/green] " f"location={handle.operation_location}")
    else:
        print(f"[green]{message} accepted[/green]")
    if handle.metadata:
        print(handle.metadata)


@app.callback()
def configure(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Governance API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    """Store shared CLI context state."""

    _state(ctx)["governance_api_version"] = api_version


@report_app.command("submit")
@handle_cli_errors
def submit_report(
    ctx: typer.Context,
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing the report request."
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Wait for the report to finish before exiting.",
    ),
    interval: float = typer.Option(
        5.0, help="Polling interval in seconds when --poll is supplied."
    ),
    timeout: float = typer.Option(
        600.0, help="Polling timeout in seconds when --poll is supplied."
    ),
) -> None:
    """Submit a cross-tenant connection report request."""

    client = _build_client(ctx)
    body = _parse_payload(payload)
    handle = client.create_cross_tenant_connection_report(body)
    _print_operation("Report submission", handle)
    if poll:
        report_id = handle.resource_id
        if not report_id:
            print("[red]Unable to determine report identifier for polling.[/red]")
            raise typer.Exit(1)
        result = client.wait_for_report(report_id, interval=interval, timeout=timeout)
        print(result)


@report_app.command("status")
@handle_cli_errors
def report_status(
    ctx: typer.Context,
    report_id: str = typer.Argument(..., help="Identifier of the submitted report"),
) -> None:
    """Retrieve a submitted cross-tenant report."""

    client = _build_client(ctx)
    payload = client.get_cross_tenant_connection_report(report_id)
    print(payload)


@report_app.command("list")
@handle_cli_errors
def list_reports(ctx: typer.Context) -> None:
    """List submitted cross-tenant connection reports."""

    client = _build_client(ctx)
    payload = client.list_cross_tenant_connection_reports()
    print(payload)


@policy_app.command("list")
@handle_cli_errors
def list_policies(ctx: typer.Context) -> None:
    """List rule-based policies."""

    client = _build_client(ctx)
    payload = client.list_rule_based_policies()
    print(payload)


@policy_app.command("create")
@handle_cli_errors
def create_policy(
    ctx: typer.Context,
    payload: str = typer.Option(..., "--payload", help="JSON payload describing the policy."),
) -> None:
    """Create a rule-based governance policy."""

    client = _build_client(ctx)
    body = _parse_payload(payload)
    result = client.create_rule_based_policy(body)
    print(result)


@policy_app.command("get")
@handle_cli_errors
def get_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Identifier of the policy to retrieve"),
) -> None:
    """Fetch a rule-based policy by identifier."""

    client = _build_client(ctx)
    payload = client.get_rule_based_policy(policy_id)
    print(payload)


@policy_app.command("update")
@handle_cli_errors
def update_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Identifier of the policy to update"),
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing the fields to update."
    ),
) -> None:
    """Update a rule-based policy."""

    client = _build_client(ctx)
    body = _parse_payload(payload)
    result = client.update_rule_based_policy(policy_id, body)
    print(result)


@assignment_app.command("create")
@handle_cli_errors
def create_assignment(
    ctx: typer.Context,
    policy_id: str = typer.Option(..., "--policy-id", help="Policy to assign."),
    environment_id: str | None = typer.Option(
        None, "--environment-id", help="Environment to assign the policy to."
    ),
    environment_group_id: str | None = typer.Option(
        None, "--environment-group-id", help="Environment group to assign the policy to."
    ),
) -> None:
    """Assign a rule-based policy to an environment or environment group."""

    if bool(environment_id) == bool(environment_group_id):
        raise typer.BadParameter(
            "Provide exactly one of --environment-id or --environment-group-id."
        )
    client = _build_client(ctx)
    if environment_group_id:
        handle = client.create_environment_group_assignment(policy_id, environment_group_id)
        _print_operation("Environment group assignment", handle)
    else:
        handle = client.create_environment_assignment(policy_id, environment_id or "")
        _print_operation("Environment assignment", handle)


@assignment_app.command("list")
@handle_cli_errors
def list_assignments(
    ctx: typer.Context,
    policy_id: str | None = typer.Option(None, "--policy-id", help="Filter by policy."),
    environment_id: str | None = typer.Option(
        None, "--environment-id", help="Filter by environment."
    ),
    environment_group_id: str | None = typer.Option(
        None, "--environment-group-id", help="Filter by environment group."
    ),
) -> None:
    """List assignments with optional filters."""

    client = _build_client(ctx)
    payload = client.list_rule_assignments(
        policy_id=policy_id,
        environment_id=environment_id,
        environment_group_id=environment_group_id,
    )
    print(payload)


@assignment_app.command("list-by-policy")
@handle_cli_errors
def list_assignments_by_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier to list assignments for"),
) -> None:
    """List assignments scoped to a policy."""

    client = _build_client(ctx)
    payload = client.list_assignments_by_policy(policy_id)
    print(payload)


@assignment_app.command("list-by-environment")
@handle_cli_errors
def list_assignments_by_environment(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment identifier"),
) -> None:
    """List assignments scoped to an environment."""

    client = _build_client(ctx)
    payload = client.list_assignments_by_environment(environment_id)
    print(payload)


@assignment_app.command("list-by-group")
@handle_cli_errors
def list_assignments_by_group(
    ctx: typer.Context,
    environment_group_id: str = typer.Argument(..., help="Environment group identifier"),
) -> None:
    """List assignments scoped to an environment group."""

    client = _build_client(ctx)
    payload = client.list_assignments_by_environment_group(environment_group_id)
    print(payload)


__all__ = [
    "app",
    "submit_report",
    "report_status",
    "list_reports",
    "list_policies",
    "create_policy",
    "get_policy",
    "update_policy",
    "create_assignment",
    "list_assignments",
    "list_assignments_by_policy",
    "list_assignments_by_environment",
    "list_assignments_by_group",
]
