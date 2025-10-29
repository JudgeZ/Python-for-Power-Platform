from __future__ import annotations

from typing import Any

import typer
from rich import print

from ..cli_utils import resolve_dataverse_host_from_context
from ..clients.dataverse import DataverseClient
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Manage connection references.")


def _client(ctx: typer.Context, host: str | None) -> DataverseClient:
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    return DataverseClient(token_getter, host=resolved_host)


@app.command("list")
@handle_cli_errors
def list_refs(
    ctx: typer.Context,
    solution: str = typer.Option(..., "--solution", help="Solution unique name"),
    host: str | None = typer.Option(None, "--host", help="Dataverse host override"),
    format: str = typer.Option("json", "--format", help="Output format: json|table"),
) -> None:
    """List connection references for a solution."""

    client = _client(ctx, host)
    refs = client.list_connection_references(solution)
    if format.lower() == "table":
        # Simple table with id / connector
        print("id\tconnector")
        for r in refs:
            print(f"{r.get('connectionid','')}\t{r.get('connectorid','')}")
    else:
        print({"value": refs})


@app.command("validate")
@handle_cli_errors
def validate_refs(
    ctx: typer.Context,
    solution: str = typer.Option(..., "--solution", help="Solution unique name"),
    host: str | None = typer.Option(None, "--host", help="Dataverse host override"),
) -> None:
    """Validate that connection references have required identifiers set."""

    client = _client(ctx, host)
    refs = client.list_connection_references(solution)
    invalid: list[dict[str, Any]] = []
    for r in refs:
        cid = r.get("connectionid")
        cnid = r.get("connectorid")
        if not cid or not cnid:
            invalid.append(r)
    ok = not invalid
    print({"ok": ok, "invalid": invalid})
    if not ok:
        raise typer.Exit(code=1)


__all__ = ["app", "list_refs", "validate_refs"]
