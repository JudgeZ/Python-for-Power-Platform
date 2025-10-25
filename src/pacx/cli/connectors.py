from __future__ import annotations

"""Typer commands that manage custom connectors."""

import typer
from rich import print

from ..cli_utils import resolve_environment_id_from_context
from ..clients.connectors import ConnectorsClient
from ..errors import HttpError
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
        None, help="Optional page size sent with the initial request"
    ),
) -> None:
    """List custom connector APIs available in an environment.

    Args:
        ctx: Active Typer context used to resolve authentication.
        environment_id: Optional environment override.
        top: Maximum number of results requested from the service.
    """

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = ConnectorsClient(token_getter)
    for page in client.iter_apis(environment, top=top):
        for item in page:
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
) -> None:
    """Retrieve the OpenAPI definition for a connector.

    Args:
        ctx: Typer context containing authentication state.
        environment_id: Optional environment override.
        api_name: Connector logical name.
    """

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
) -> None:
    """Create or update a connector from an OpenAPI document.

    Args:
        ctx: Typer context containing authentication state.
        environment_id: Optional environment override.
        name: Connector logical name.
        openapi_path: Location of the OpenAPI document to import.
        display_name: Optional friendly display name.
    """

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    with open(openapi_path, encoding="utf-8") as handle:
        text = handle.read()
    client = ConnectorsClient(token_getter)
    result = client.put_api_from_openapi(environment, name, text, display_name=display_name)
    print(result)


@app.command("delete")
@handle_cli_errors
def connector_delete(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    api_name: str = typer.Argument(..., help="API (connector) internal name"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Confirm deletion without prompting.",
    ),
) -> None:
    """Delete a connector from the target environment.

    Args:
        ctx: Typer context containing authentication state.
        environment_id: Optional environment override.
        api_name: Connector logical name.
        yes: When ``True`` skips the confirmation prompt.
    """

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    if not yes:
        confirmed = typer.confirm(
            f"Delete connector '{api_name}' from environment '{environment}'?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit(0)
    client = ConnectorsClient(token_getter)
    try:
        client.delete_api(environment, api_name)
    except HttpError as exc:
        if exc.status_code == 404:
            print(
                f"[red]Connector '{api_name}' was not found in environment '{environment}'.[/red]"
            )
            raise typer.Exit(1) from None
        raise
    print(f"[green]Deleted connector '{api_name}' from environment '{environment}'.[/green]")


__all__ = [
    "app",
    "connectors_list",
    "connectors_get",
    "connector_push",
    "connector_delete",
]
