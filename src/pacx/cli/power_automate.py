"""Typer commands for Power Automate cloud flows."""

from __future__ import annotations

from typing import Any

import typer
from rich import print

from ..clients.power_automate import DEFAULT_API_VERSION, PowerAutomateClient
from ..models.power_automate import CloudFlowState, CloudFlowStatePatch
from ..models.power_platform import CloudFlow
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Power Automate cloud flows")

_STATE_KEY = "power_automate_api_version"
_STATE_CHOICES: dict[str, CloudFlowState] = {
    "started": "Started",
    "stopped": "Stopped",
    "suspended": "Suspended",
}


def _context_state(ctx: typer.Context) -> dict[str, Any]:
    return ctx.ensure_object(dict)


def _current_version(ctx: typer.Context) -> str:
    version = _context_state(ctx).get(_STATE_KEY, DEFAULT_API_VERSION)
    if isinstance(version, str) and version:
        return version
    return DEFAULT_API_VERSION


def _client(ctx: typer.Context) -> PowerAutomateClient:
    token_getter = get_token_getter(ctx)
    return PowerAutomateClient(token_getter, api_version=_current_version(ctx))


def _render_flow(flow: CloudFlow) -> dict[str, Any]:
    return flow.model_dump(by_alias=True, exclude_none=True)


@app.callback()
def configure(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Power Automate API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    """Store shared CLI context state."""

    _context_state(ctx)[_STATE_KEY] = api_version


@app.command("list")
@handle_cli_errors
def list_flows(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Power Platform environment ID"),
    workflow_id: str | None = typer.Option(None, help="Filter by workflow ID (GUID)."),
    resource_id: str | None = typer.Option(None, help="Filter by resource ID (GUID)."),
    created_by: str | None = typer.Option(None, help="Filter by creator Dataverse ID."),
    owner_id: str | None = typer.Option(None, help="Filter by owner Dataverse ID."),
    modified_on_start: str | None = typer.Option(
        None,
        help="Return flows modified on or after this ISO date (YYYY-MM-DD).",
    ),
    modified_on_end: str | None = typer.Option(
        None,
        help="Return flows modified on or before this ISO date (YYYY-MM-DD).",
    ),
    continuation_token: str | None = typer.Option(
        None,
        "--continuation-token",
        help="Continue from a previous response using the X-MS-Continuation-Token header.",
    ),
) -> None:
    """List cloud flows for an environment."""

    with _client(ctx) as client:
        page = client.list_cloud_flows(
            environment_id,
            workflow_id=workflow_id,
            resource_id=resource_id,
            created_by=created_by,
            owner_id=owner_id,
            modified_on_start_date=modified_on_start,
            modified_on_end_date=modified_on_end,
            continuation_token=continuation_token,
        )
    if page.is_empty():
        print("[yellow]No cloud flows found.[/yellow]")
        return
    print([_render_flow(flow) for flow in page.flows])
    if page.continuation_token:
        print(f"[green]Continuation token:[/green] {page.continuation_token}")


@app.command("get")
@handle_cli_errors
def get_flow(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Power Platform environment ID"),
    flow_id: str = typer.Argument(..., help="Cloud flow identifier (GUID)."),
) -> None:
    """Retrieve metadata for a single cloud flow."""

    with _client(ctx) as client:
        flow = client.get_cloud_flow(environment_id, flow_id)
    print(_render_flow(flow))


@app.command("set-state")
@handle_cli_errors
def set_flow_state(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Power Platform environment ID"),
    flow_id: str = typer.Argument(..., help="Cloud flow identifier (GUID)."),
    state: str = typer.Option(
        ...,  # required
        case_sensitive=False,
        prompt=True,
        help="Desired state (Started, Stopped, Suspended).",
    ),
) -> None:
    """Update the execution state of a cloud flow."""

    normalized = state.strip().lower()
    if normalized not in _STATE_CHOICES:
        raise typer.BadParameter("State must be one of: " + ", ".join(sorted(_STATE_CHOICES)))
    patch = CloudFlowStatePatch(state=_STATE_CHOICES[normalized])
    with _client(ctx) as client:
        flow = client.set_cloud_flow_state(environment_id, flow_id, patch)
    print(_render_flow(flow))


@app.command("delete")
@handle_cli_errors
def delete_flow(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Power Platform environment ID"),
    flow_id: str = typer.Argument(..., help="Cloud flow identifier (GUID)."),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Confirm deletion without prompting.",
    ),
) -> None:
    """Delete a cloud flow."""

    if not yes:
        typer.confirm("Delete cloud flow?", abort=True)
    with _client(ctx) as client:
        client.delete_cloud_flow(environment_id, flow_id)
    print("[green]Cloud flow deleted.[/green]")


__all__ = ["app", "set_flow_state", "get_flow", "delete_flow", "list_flows"]
