"""Typer commands that manage custom connectors."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import TypeVar

import typer
from rich import print

from ..cli_utils import resolve_environment_id_from_context
from ..clients.connectors import ConnectorsClient
from ..errors import HttpError
from .common import get_token_getter, handle_cli_errors

# Connectivity calls fail with 401/403 when the caller lacks the scopes required for
# the new endpoints. 404/405 are returned when the feature flag is disabled or the
# route is not implemented in the current region. Treat them all as signals to
# retry against the legacy Power Apps endpoints when the CLI is configured to
# allow fallback.
_CONNECTIVITY_FALLBACK_STATUS = frozenset({401, 403, 404, 405})

T = TypeVar("T")


class EndpointChoice(str, Enum):
    """CLI switch controlling which connector API family to target."""

    AUTO = "auto"
    POWERAPPS = "powerapps"
    CONNECTIVITY = "connectivity"


app = typer.Typer(help="Connectors (APIs)")


def _with_endpoint(
    token_getter: Callable[[], str],
    choice: EndpointChoice,
    *,
    prefer_connectivity: bool,
    fallback_on_404: bool,
    action: Callable[[ConnectorsClient], T],
) -> T:
    """Execute an action against the chosen connector endpoint variant."""

    if choice == EndpointChoice.AUTO:
        primary = ConnectorsClient(token_getter, use_connectivity=prefer_connectivity)
        try:
            return action(primary)
        except HttpError as exc:
            if (
                prefer_connectivity
                and fallback_on_404
                and exc.status_code in _CONNECTIVITY_FALLBACK_STATUS
            ):
                fallback = ConnectorsClient(token_getter, use_connectivity=False)
                return action(fallback)
            raise
        except AssertionError:
            if prefer_connectivity and fallback_on_404:
                fallback = ConnectorsClient(token_getter, use_connectivity=False)
                return action(fallback)
            raise
    client = ConnectorsClient(token_getter, use_connectivity=choice == EndpointChoice.CONNECTIVITY)
    return action(client)


@app.command("list")
@handle_cli_errors
def connectors_list(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(  # noqa: B008
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    top: int | None = typer.Option(  # noqa: B008
        None, help="Optional page size sent with the initial request"
    ),
    endpoint: EndpointChoice = typer.Option(  # noqa: B008
        EndpointChoice.AUTO,
        "--endpoint",
        help="Connector API family (auto, powerapps, connectivity)",
        case_sensitive=False,
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

    def run(client: ConnectorsClient) -> None:
        for page in client.iter_apis(environment, top=top):
            for item in page:
                name = item.get("name") or item.get("id")
                print(f"[bold]{name}[/bold]")

    _with_endpoint(
        token_getter,
        endpoint,
        prefer_connectivity=True,
        fallback_on_404=True,
        action=run,
    )


@app.command("get")
@handle_cli_errors
def connectors_get(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(  # noqa: B008
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    api_name: str = typer.Argument(..., help="API (connector) internal name"),
    endpoint: EndpointChoice = typer.Option(  # noqa: B008
        EndpointChoice.AUTO,
        "--endpoint",
        help="Connector API family (auto, powerapps, connectivity)",
        case_sensitive=False,
    ),
) -> None:
    """Retrieve the OpenAPI definition for a connector.

    Args:
        ctx: Typer context containing authentication state.
        environment_id: Optional environment override.
        api_name: Connector logical name.
    """

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)

    def run(client: ConnectorsClient) -> None:
        data = client.get_api(environment, api_name)
        print(data)

    _with_endpoint(
        token_getter,
        endpoint,
        prefer_connectivity=True,
        fallback_on_404=True,
        action=run,
    )


@app.command("push")
@handle_cli_errors
def connector_push(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(  # noqa: B008
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    name: str = typer.Option(
        ..., "--name", help="Connector internal name to create/update"
    ),  # noqa: B008
    openapi_path: str = typer.Option(  # noqa: B008
        ..., "--openapi", help="Path to OpenAPI/Swagger file (YAML or JSON)"
    ),
    display_name: str | None = typer.Option(  # noqa: B008
        None, help="Optional friendly name shown in Power Platform"
    ),
    endpoint: EndpointChoice = typer.Option(  # noqa: B008
        EndpointChoice.AUTO,
        "--endpoint",
        help="Connector API family (auto, powerapps, connectivity)",
        case_sensitive=False,
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
    text = Path(openapi_path).read_text(encoding="utf-8")

    def run(client: ConnectorsClient) -> None:
        result = client.put_api_from_openapi(environment, name, text, display_name=display_name)
        print(result)

    _with_endpoint(
        token_getter,
        endpoint,
        prefer_connectivity=True,
        fallback_on_404=True,
        action=run,
    )


@app.command("delete")
@handle_cli_errors
def connector_delete(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(  # noqa: B008
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    api_name: str = typer.Argument(..., help="API (connector) internal name"),
    yes: bool = typer.Option(  # noqa: B008
        False,
        "--yes",
        "-y",
        help="Confirm deletion without prompting.",
    ),
    endpoint: EndpointChoice = typer.Option(  # noqa: B008
        EndpointChoice.AUTO,
        "--endpoint",
        help="Connector API family (auto, powerapps, connectivity)",
        case_sensitive=False,
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
    try:
        _with_endpoint(
            token_getter,
            endpoint,
            prefer_connectivity=True,
            fallback_on_404=True,
            action=lambda client: client.delete_api(environment, api_name),
        )
    except HttpError as exc:
        if exc.status_code == 404:
            print(
                f"[red]Connector '{api_name}' was not found in environment '{environment}'.[/red]"
            )
            raise typer.Exit(1) from None
        raise
    print(f"[green]Deleted connector '{api_name}' from environment '{environment}'.[/green]")


@app.command("validate")
@handle_cli_errors
def connector_validate(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(  # noqa: B008
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    name: str = typer.Option(..., "--name", help="Connector internal name"),  # noqa: B008
    openapi_path: str = typer.Option(  # noqa: B008
        ..., "--openapi", help="Path to OpenAPI/Swagger file (YAML or JSON)"
    ),
    display_name: str | None = typer.Option(  # noqa: B008
        None, help="Optional friendly name used during validation"
    ),
    endpoint: EndpointChoice = typer.Option(  # noqa: B008
        EndpointChoice.AUTO,
        "--endpoint",
        help="Connector API family (auto or connectivity)",
        case_sensitive=False,
    ),
) -> None:
    """Validate a connector definition using the connectivity endpoints."""

    if endpoint == EndpointChoice.POWERAPPS:
        print(
            "[red]Validation requires the connectivity endpoints (--endpoint connectivity).[/red]"
        )
        raise typer.Exit(2)

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    text = Path(openapi_path).read_text(encoding="utf-8")

    def run(client: ConnectorsClient) -> None:
        result = client.validate_custom_connector_from_openapi(
            environment, name, text, display_name=display_name
        )
        print(result)

    _with_endpoint(
        token_getter,
        endpoint,
        prefer_connectivity=True,
        fallback_on_404=False,
        action=run,
    )


@app.command("runtime-status")
@handle_cli_errors
def connector_runtime_status(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(  # noqa: B008
        None, help="Environment ID to target (defaults to profile configuration)"
    ),
    api_name: str = typer.Argument(..., help="Connector internal name"),
    endpoint: EndpointChoice = typer.Option(  # noqa: B008
        EndpointChoice.AUTO,
        "--endpoint",
        help="Connector API family (auto or connectivity)",
        case_sensitive=False,
    ),
) -> None:
    """Display the runtime health for a custom connector."""

    if endpoint == EndpointChoice.POWERAPPS:
        print(
            "[red]Runtime status is only exposed by the connectivity endpoints (--endpoint connectivity or auto).[/red]"
        )
        raise typer.Exit(2)

    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)

    def run(client: ConnectorsClient) -> None:
        status = client.get_custom_connector_runtime_status(environment, api_name)
        print(status)

    _with_endpoint(
        token_getter,
        endpoint,
        prefer_connectivity=True,
        fallback_on_404=False,
        action=run,
    )


__all__ = [
    "app",
    "connectors_list",
    "connectors_get",
    "connector_push",
    "connector_delete",
    "connector_validate",
    "connector_runtime_status",
]
