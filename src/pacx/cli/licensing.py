from __future__ import annotations

import json
from typing import Any, cast

import typer
from rich import print

from ..clients.licensing import DEFAULT_API_VERSION, LicensingClient, LicensingOperation
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Power Platform licensing operations")
billing_app = typer.Typer(help="Manage billing policies", invoke_without_command=True)
billing_env_app = typer.Typer(help="Manage billing policy environment associations")
allocations_app = typer.Typer(help="Manage currency and capacity allocations")
currency_app = typer.Typer(help="Currency allocations")
capacity_alloc_app = typer.Typer(help="Environment capacity allocations")
storage_app = typer.Typer(help="Inspect storage warnings")
capacity_app = typer.Typer(help="Capacity snapshots and summaries")


def _resolve_client_class() -> type[LicensingClient]:
    module = __import__("pacx.cli", fromlist=["LicensingClient"])
    client_cls = getattr(module, "LicensingClient", LicensingClient)
    return cast(type[LicensingClient], client_cls)


def _build_client(ctx: typer.Context, api_version: str) -> LicensingClient:
    token_getter = get_token_getter(ctx)
    client_cls = _resolve_client_class()
    return client_cls(token_getter, api_version=api_version)


def _ensure_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["licensing_api_version"] = override
        return override
    return cast(str, data.get("licensing_api_version", DEFAULT_API_VERSION))


def _parse_payload(raw: str | None) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    raw_str = cast(str, raw)
    try:
        payload = json.loads(raw_str)
    except json.JSONDecodeError as exc:  # pragma: no cover - validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Payload must be a JSON object")
    return cast(dict[str, Any], payload)


def _print_operation(action: str, handle: LicensingOperation) -> None:
    if handle.operation_location:
        print(
            f"[green]{action} accepted[/green] operation={handle.operation_id} "
            f"location={handle.operation_location}"
        )
    else:
        print(f"[green]{action} accepted[/green]")
    if handle.metadata:
        print(handle.metadata)


@app.callback()
@handle_cli_errors
def licensing_root(
    ctx: typer.Context,
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Licensing API version (defaults to 2022-03-01-preview)",
    ),
) -> None:
    """Store shared API version for licensing subcommands."""

    ctx.ensure_object(dict)["licensing_api_version"] = api_version


@billing_app.callback(invoke_without_command=True)
@handle_cli_errors
def billing_root(
    ctx: typer.Context,
    api_version: str | None = typer.Option(
        None, help="Licensing API version override for billing policy commands"
    ),
) -> None:
    version = _ensure_api_version(ctx, api_version)
    if ctx.invoked_subcommand is None:
        list_policies(ctx, api_version=version)


@billing_app.command("list")
@handle_cli_errors
def list_policies(
    ctx: typer.Context,
    api_version: str | None = typer.Option(
        None, help="Licensing API version override for billing policy commands"
    ),
) -> None:
    """List billing policies configured for the tenant."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    policies = client.list_billing_policies()
    for policy in policies:
        identifier = policy.get("id") or policy.get("name")
        print(f"[bold]{identifier or 'unknown-policy'}[/bold]")


@billing_app.command("get")
@handle_cli_errors
def get_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve a billing policy."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_billing_policy(policy_id)
    print(data)


@billing_app.command("create")
@handle_cli_errors
def create_policy(
    ctx: typer.Context,
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing the billing policy"
    ),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Create a new billing policy."""

    version = _ensure_api_version(ctx, api_version)
    body = _parse_payload(payload)
    client = _build_client(ctx, version)
    data = client.create_billing_policy(body)
    print(data)


@billing_app.command("update")
@handle_cli_errors
def update_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    payload: str = typer.Option(..., "--payload", help="JSON payload for the update"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Update an existing billing policy."""

    version = _ensure_api_version(ctx, api_version)
    body = _parse_payload(payload)
    client = _build_client(ctx, version)
    data = client.update_billing_policy(policy_id, body)
    print(data)


@billing_app.command("delete")
@handle_cli_errors
def delete_policy(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Confirm deletion without prompting",
    ),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Delete a billing policy."""

    if not yes:
        confirmed = typer.confirm(f"Delete billing policy '{policy_id}'?", default=False)
        if not confirmed:
            raise typer.Exit(0)
    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    client.delete_billing_policy(policy_id)
    print(f"[green]Deleted billing policy '{policy_id}'.[/green]")


@billing_app.command("refresh-provisioning")
@handle_cli_errors
def refresh_provisioning(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    wait: bool = typer.Option(
        False, "--wait/--no-wait", help="Poll the operation until completion"
    ),
    interval: float = typer.Option(2.0, help="Polling interval in seconds"),
    timeout: float = typer.Option(600.0, help="Polling timeout in seconds"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Refresh billing policy provisioning status."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    handle = client.refresh_billing_policy_provisioning(policy_id)
    _print_operation("Provisioning refresh", handle)
    if wait:
        if not handle.operation_location:
            print("[yellow]No operation location returned; skipping wait.[/yellow]")
            return
        final = client.wait_for_operation(
            handle.operation_location, interval=interval, timeout=timeout
        )
        print(final)


@billing_app.command("environment-default")
@handle_cli_errors
def get_environment_default(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve the default billing policy for an environment."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_environment_billing_policy(environment_id)
    print(data)


@billing_env_app.command("list")
@handle_cli_errors
def list_policy_environments(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """List environments linked to a billing policy."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    environments = client.list_billing_policy_environments(policy_id)
    for env in environments:
        identifier = env.get("id") or env.get("name")
        print(f"[bold]{identifier or 'unknown-environment'}[/bold]")


@billing_env_app.command("get")
@handle_cli_errors
def get_policy_environment(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve billing policy association metadata for an environment."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_billing_policy_environment(policy_id, environment_id)
    print(data)


@billing_env_app.command("add")
@handle_cli_errors
def add_policy_environment(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Associate an environment with a billing policy."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    client.add_billing_policy_environment(policy_id, environment_id)
    print(f"[green]Added environment '{environment_id}' to billing policy '{policy_id}'.[/green]")


@billing_env_app.command("remove")
@handle_cli_errors
def remove_policy_environment(
    ctx: typer.Context,
    policy_id: str = typer.Argument(..., help="Billing policy identifier"),
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Remove an environment from a billing policy."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    client.remove_billing_policy_environment(policy_id, environment_id)
    print(
        f"[green]Removed environment '{environment_id}' from billing policy '{policy_id}'.[/green]"
    )


@currency_app.command("get")
@handle_cli_errors
def get_currency_allocation(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve currency allocation for an environment."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_currency_allocation(environment_id)
    print(data)


@currency_app.command("patch")
@handle_cli_errors
def patch_currency_allocation(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    payload: str = typer.Option(
        ..., "--payload", help="JSON payload describing allocation changes"
    ),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Patch the currency allocation for an environment."""

    version = _ensure_api_version(ctx, api_version)
    body = _parse_payload(payload)
    client = _build_client(ctx, version)
    data = client.patch_currency_allocation(environment_id, body)
    print(data)


@allocations_app.command("reports")
@handle_cli_errors
def list_currency_reports(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """List currency allocation reports."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    reports = client.list_currency_reports()
    for report in reports:
        identifier = report.get("id") or report.get("name")
        print(f"[bold]{identifier or 'report'}[/bold]")


@capacity_alloc_app.command("get")
@handle_cli_errors
def get_environment_capacity(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve capacity allocations for an environment."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_environment_allocations(environment_id)
    print(data)


@capacity_alloc_app.command("patch")
@handle_cli_errors
def patch_environment_capacity(
    ctx: typer.Context,
    environment_id: str = typer.Argument(..., help="Environment identifier"),
    payload: str = typer.Option(..., "--payload", help="JSON payload describing capacity updates"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Patch capacity allocations for an environment."""

    version = _ensure_api_version(ctx, api_version)
    body = _parse_payload(payload)
    client = _build_client(ctx, version)
    data = client.update_environment_allocations(environment_id, body)
    print(data)


@storage_app.command("list")
@handle_cli_errors
def list_storage(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """List storage warnings for the tenant."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    warnings = client.list_storage_warnings()
    for warning in warnings:
        category = warning.get("category") or warning.get("id")
        print(f"[bold]{category or 'warning'}[/bold]")


@storage_app.command("get")
@handle_cli_errors
def get_storage_category(
    ctx: typer.Context,
    category: str = typer.Argument(..., help="Storage warning category"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve storage warning details for a category."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_storage_warning(category)
    print(data)


@storage_app.command("entity")
@handle_cli_errors
def get_storage_entity(
    ctx: typer.Context,
    category: str = typer.Argument(..., help="Storage warning category"),
    entity: str = typer.Argument(..., help="Entity identifier"),
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve storage warning details for a specific entity."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_storage_warning_entity(category, entity)
    print(data)


@capacity_app.command("tenant")
@handle_cli_errors
def get_tenant_capacity(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve tenant capacity details."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_tenant_capacity_details()
    print(data)


@capacity_app.command("temporary-currency")
@handle_cli_errors
def get_temporary_currency(
    ctx: typer.Context,
    api_version: str | None = typer.Option(None, help="Licensing API version override"),
) -> None:
    """Retrieve temporary currency entitlement counts."""

    version = _ensure_api_version(ctx, api_version)
    client = _build_client(ctx, version)
    data = client.get_temporary_currency_entitlement_count()
    print(data)


# Register nested command groups
billing_app.add_typer(billing_env_app, name="environment")
allocations_app.add_typer(currency_app, name="currency")
allocations_app.add_typer(capacity_alloc_app, name="capacity")
app.add_typer(billing_app, name="billing")
app.add_typer(allocations_app, name="allocations")
app.add_typer(storage_app, name="storage")
app.add_typer(capacity_app, name="capacity")


__all__ = [
    "app",
    "billing_app",
    "billing_env_app",
    "allocations_app",
    "currency_app",
    "capacity_alloc_app",
    "storage_app",
    "capacity_app",
    "LicensingClient",
]
