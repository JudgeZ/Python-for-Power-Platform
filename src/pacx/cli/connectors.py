from __future__ import annotations

import typer
from rich import print

from ..clients.connectors import ConnectorsClient
from ..cli_utils import resolve_environment_id_from_context
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Connectors (APIs)")


@app.command("list")
@handle_cli_errors
def connectors_list(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    top: int | None = typer.Option(
        None, help="Maximum results to return via $top (default: server limit)"
    ),
):
    """List custom connector APIs available in an environment."""

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = ConnectorsClient(token_getter)
    data = client.list_apis(environment, top=top)
    for item in data.get("value") or []:
        name = item.get("name") or item.get("id")
        print(f"[bold]{name}[/bold]")


@app.command("get")
@handle_cli_errors
def connectors_get(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    api_name: str = typer.Argument(..., help="API (connector) internal name"),
):
    """Retrieve the OpenAPI definition for a connector."""

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = ConnectorsClient(token_getter)
    data = client.get_api(environment, api_name)
    print(data)


@app.command("push")
@handle_cli_errors
def connector_push(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    name: str = typer.Option(..., "--name", help="Connector internal name to create/update"),
    openapi_path: str = typer.Option(
        ..., "--openapi", help="Path to OpenAPI/Swagger file (YAML or JSON)"
    ),
    display_name: str | None = typer.Option(
        None, help="Optional friendly name shown in Power Platform"
    ),
):
    """Create or update a connector from an OpenAPI document."""

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    with open(openapi_path, encoding="utf-8") as handle:
        text = handle.read()
    client = ConnectorsClient(token_getter)
    result = client.put_api_from_openapi(environment, name, text, display_name=display_name)
    print(result)


__all__ = ["app", "connectors_list", "connectors_get", "connector_push"]
