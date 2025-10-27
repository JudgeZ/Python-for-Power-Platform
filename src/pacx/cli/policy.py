"""CLI commands for Data Loss Prevention policies."""

from __future__ import annotations

import json
import os
import re
from typing import Any, cast

import typer

from ..cli_utils import get_config_from_context
from ..clients.policy import (
    DEFAULT_API_VERSION,
    DataLossPreventionClient,
    PolicyOperationHandle,
    PolicyPage,
)
from ..config import Profile
from ..models.policy import ConnectorGroup, DataLossPreventionPolicy, PolicyAssignment
from .common import console, get_token_getter, handle_cli_errors

READ_SCOPES = ("Policy.DataLossPrevention.Read",)
MANAGE_SCOPES = ("Policy.DataLossPrevention.Manage",)

app = typer.Typer(help="Manage policy administration workloads.")
dlp_app = typer.Typer(
    help="Manage data loss prevention (DLP) policies.", invoke_without_command=True
)
connectors_app = typer.Typer(help="Manage DLP connector classifications.")
assignments_app = typer.Typer(help="Manage DLP environment assignments.")

app.add_typer(dlp_app, name="dlp")
dlp_app.add_typer(connectors_app, name="connectors")
dlp_app.add_typer(assignments_app, name="assignments")


def _collect_scopes(profile: Profile) -> set[str]:
    values: set[str] = set()
    raw_values: list[str] = []
    if profile.scope:
        raw_values.append(profile.scope)
    if profile.scopes:
        raw_values.extend(profile.scopes)
    for entry in raw_values:
        for token in re.split(r"[\s,]+", entry or ""):
            if token:
                values.add(token)
    return values


def _get_active_profile(ctx: typer.Context) -> Profile:
    cfg = get_config_from_context(ctx)
    name = cfg.default_profile
    if not name or name not in cfg.profiles:
        raise typer.BadParameter(
            "No default profile configured. Run `ppx auth use <profile>` to activate credentials."
        )
    return cfg.profiles[name]


def _ensure_required_scopes(ctx: typer.Context, required: tuple[str, ...]) -> None:
    if os.getenv("PACX_ACCESS_TOKEN"):
        return
    profile = _get_active_profile(ctx)
    scopes = _collect_scopes(profile)
    missing = [scope for scope in required if scope not in scopes]
    if missing:
        joined = ", ".join(missing)
        raise typer.BadParameter(
            "Active profile missing required scope(s): "
            f"{joined}. Update the profile via `ppx auth update --scopes`."
        )


def _build_client(ctx: typer.Context, *, api_version: str) -> DataLossPreventionClient:
    token_getter = get_token_getter(ctx)
    client_cls = DataLossPreventionClient
    return client_cls(token_getter, api_version=api_version)


def _ensure_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["policy_api_version"] = override
        return override
    cached = data.get("policy_api_version")
    if isinstance(cached, str) and cached:
        return cached
    data["policy_api_version"] = DEFAULT_API_VERSION
    return DEFAULT_API_VERSION


def _parse_payload(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        raise typer.BadParameter("Provide a JSON object via --payload.")
    raw_str = cast(str, raw)
    try:
        payload = json.loads(raw_str)
    except json.JSONDecodeError as exc:  # pragma: no cover - validated through Typer option
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return payload


def _print_policy_summary(policy: DataLossPreventionPolicy) -> None:
    parts = [
        f"id={policy.id}" if policy.id else None,
        f"state={policy.state}",
        f"scope={policy.policy_scope}" if policy.policy_scope else None,
    ]
    details = "  ".join(part for part in parts if part)
    console.print(f"[bold]{policy.display_name}[/bold]{('  ' + details) if details else ''}")


def _print_policy_page(page: PolicyPage) -> None:
    if not page.policies:
        console.print("[yellow]No policies found.[/yellow]")
        return
    for policy in page.policies:
        _print_policy_summary(policy)
    if page.next_link:
        console.print(f"[cyan]Next page:[/cyan] {page.next_link}")


def _render_operation(
    client: DataLossPreventionClient,
    action: str,
    handle: PolicyOperationHandle,
    *,
    wait: bool,
    interval: float = 2.0,
    timeout: float = 600.0,
) -> None:
    if wait and handle.operation_location:
        result = client.wait_for_operation(
            handle.operation_location, interval=interval, timeout=timeout
        )
        console.print(f"[green]{action} completed[/green] status={result.status}")
        console.print(json.dumps(result.model_dump(by_alias=True, exclude_none=True), indent=2))
        return

    message = f"[green]{action} accepted[/green]"
    if handle.operation_id:
        message += f" operation={handle.operation_id}"
    console.print(message)
    if handle.operation is not None:
        console.print(
            json.dumps(handle.operation.model_dump(by_alias=True, exclude_none=True), indent=2)
        )


@dlp_app.callback(invoke_without_command=True)
@handle_cli_errors
def dlp_root(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Policy API version (defaults to 2023-10-01-preview)",
    ),
) -> None:
    ctx.ensure_object(dict)["policy_api_version"] = api_version
    if ctx.invoked_subcommand is None:
        list_policies(ctx, api_version=api_version)


@dlp_app.command("list")
@handle_cli_errors
def list_policies(
    ctx: typer.Context,
    top: int | None = typer.Option(None, help="Optional page size limit."),
    skip: int | None = typer.Option(None, help="Optional offset for pagination."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """List DLP policies available to the tenant."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, READ_SCOPES)
    client = _build_client(ctx, api_version=version)
    page = client.list_policies(top=top, skip=skip)
    _print_policy_page(page)


@dlp_app.command("get")
@handle_cli_errors
def get_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Retrieve a single DLP policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, READ_SCOPES)
    client = _build_client(ctx, api_version=version)
    policy = client.get_policy(policy_id)
    console.print(json.dumps(policy.model_dump(by_alias=True, exclude_none=True), indent=2))


@dlp_app.command("create")
@handle_cli_errors
def create_policy(
    ctx: typer.Context,
    payload: str = typer.Option(..., "--payload", help="JSON payload describing the policy."),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for operation completion."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Create a new DLP policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, MANAGE_SCOPES)
    data = _parse_payload(payload)
    policy = DataLossPreventionPolicy.model_validate(data)
    client = _build_client(ctx, api_version=version)
    handle = client.create_policy(policy)
    _render_operation(client, "Policy creation", handle, wait=wait)


@dlp_app.command("update")
@handle_cli_errors
def update_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing the policy changes."
    ),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for operation completion."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Update an existing DLP policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, MANAGE_SCOPES)
    data = _parse_payload(payload)
    policy = DataLossPreventionPolicy.model_validate(data)
    client = _build_client(ctx, api_version=version)
    handle = client.update_policy(policy_id, policy)
    _render_operation(client, "Policy update", handle, wait=wait)


@dlp_app.command("delete")
@handle_cli_errors
def delete_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for operation completion."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Delete a DLP policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, MANAGE_SCOPES)
    client = _build_client(ctx, api_version=version)
    handle = client.delete_policy(policy_id)
    _render_operation(client, "Policy deletion", handle, wait=wait)


@connectors_app.command("list")
@handle_cli_errors
def list_connector_groups(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """List connector group classifications for a policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, READ_SCOPES)
    client = _build_client(ctx, api_version=version)
    groups = client.list_connector_groups(policy_id)
    if not groups:
        console.print("[yellow]No connector groups configured.[/yellow]")
        return
    for group in groups:
        connector_ids = ", ".join(connector.id for connector in group.connectors)
        console.print(
            f"[bold]{group.classification}[/bold] connectors=[{connector_ids}]"
            if connector_ids
            else f"[bold]{group.classification}[/bold] (no connectors)"
        )


@connectors_app.command("update")
@handle_cli_errors
def update_connector_groups(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    payload: str = typer.Option(..., "--payload", help="JSON payload containing a `groups` array."),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for operation completion."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Replace connector group assignments for a policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, MANAGE_SCOPES)
    data = _parse_payload(payload)
    groups_payload = data.get("groups")
    if not isinstance(groups_payload, list) or not groups_payload:
        raise typer.BadParameter("Payload must include a non-empty `groups` array.")
    groups = [ConnectorGroup.model_validate(item) for item in groups_payload]
    client = _build_client(ctx, api_version=version)
    handle = client.update_connector_groups(policy_id, groups)
    _render_operation(client, "Connector groups update", handle, wait=wait)


@assignments_app.command("list")
@handle_cli_errors
def list_assignments(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """List environment assignments for a policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, READ_SCOPES)
    client = _build_client(ctx, api_version=version)
    assignments = client.list_assignments(policy_id)
    if not assignments:
        console.print("[yellow]No assignments found.[/yellow]")
        return
    for assignment in assignments:
        console.print(f"[bold]{assignment.environment_id}[/bold] type={assignment.assignment_type}")


@assignments_app.command("assign")
@handle_cli_errors
def assign_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    payload: str = typer.Option(..., "--payload", help="JSON payload with an `assignments` array."),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for operation completion."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Assign a policy to one or more environments."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, MANAGE_SCOPES)
    data = _parse_payload(payload)
    assignments_payload = data.get("assignments")
    if not isinstance(assignments_payload, list) or not assignments_payload:
        raise typer.BadParameter("Payload must include a non-empty `assignments` array.")
    assignments = [PolicyAssignment.model_validate(item) for item in assignments_payload]
    client = _build_client(ctx, api_version=version)
    handle = client.assign_policy(policy_id, assignments)
    _render_operation(client, "Policy assignment", handle, wait=wait)


@assignments_app.command("remove")
@handle_cli_errors
def remove_assignment(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Policy identifier."),
    assignment_id: str = typer.Argument(..., help="Assignment identifier to remove."),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for operation completion."),
    api_version: str | None = typer.Option(None, help="Policy API version override."),
) -> None:
    """Remove an environment assignment from a policy."""

    version = _ensure_api_version(ctx, api_version)
    _ensure_required_scopes(ctx, MANAGE_SCOPES)
    client = _build_client(ctx, api_version=version)
    handle = client.remove_assignment(policy_id, assignment_id)
    _render_operation(client, "Policy assignment removal", handle, wait=wait)


__all__ = [
    "app",
    "assign_policy",
    "create_policy",
    "delete_policy",
    "dlp_app",
    "get_policy",
    "list_assignments",
    "list_connector_groups",
    "list_policies",
    "remove_assignment",
    "update_connector_groups",
    "update_policy",
]
