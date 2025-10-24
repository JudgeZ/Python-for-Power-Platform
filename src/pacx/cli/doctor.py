from __future__ import annotations

import os

import typer
from rich import print

from ..cli_utils import get_config_from_context
from ..clients.dataverse import DataverseClient
from .common import handle_cli_errors, resolve_token_getter


def register(app: typer.Typer) -> None:
    app.command("doctor")(doctor)


@handle_cli_errors
def doctor(
    ctx: typer.Context,
    host: str | None = typer.Option(
        None,
        help=(
            "Dataverse host to probe (defaults to profile, DATAVERSE_HOST, or skips if unset)"
        ),
    ),
    check_dataverse: bool = typer.Option(
        True,
        help="Attempt Dataverse connectivity test (disable with --no-check-dataverse)",
    ),
):
    """Validate PACX environment configuration."""

    cfg = get_config_from_context(ctx)
    ok = True
    if cfg.default_profile:
        print(f"[green]Default profile:[/green] {cfg.default_profile}")
    else:
        print("[yellow]No default profile configured.[/yellow]")
    try:
        token_getter = resolve_token_getter(config=cfg)
        token_preview = token_getter()
        print("[green]Token acquisition successful.[/green]")
        ctx.obj["token_getter"] = lambda: token_preview
    except Exception as exc:  # pragma: no cover - error path tested separately
        print(f"[red]Token acquisition failed:[/red] {exc}")
        ok = False
        token_getter = None

    if check_dataverse and token_getter:
        host_value = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
        if not host_value:
            print("[yellow]Skipping Dataverse probe: host unknown.[/yellow]")
        else:
            try:
                dv = DataverseClient(lambda: token_preview, host=host_value)
                who = dv.whoami()
                print(f"[green]Dataverse reachable:[/green] {who.get('UserId', 'unknown')}")
            except Exception as exc:  # pragma: no cover - network failures
                print(f"[red]Dataverse probe failed:[/red] {exc}")
                ok = False

    raise typer.Exit(code=0 if ok else 1)


__all__ = ["register", "doctor"]
