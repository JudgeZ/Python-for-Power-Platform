"""CoE (Center of Excellence) command group.

Provides lightweight inventory, makers, metrics, and export helpers. The
underlying :class:`pacx.clients.coe.CoeClient` is intentionally minimal and is
stubbed in tests. Output formats follow repository conventions: JSON by default
and CSV via the export subcommand.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import typer

from ..clients.coe import CoeClient
from .common import console, get_token_getter, handle_cli_errors

app = typer.Typer(help="Center of Excellence insights and exports.")

ENVIRONMENT_ID_OPTION = typer.Option(
    None, "--environment-id", "-e", help="Filter by environment ID."
)
RESOURCE_OPTION = typer.Option(
    ..., "--resource", "-r", help="Which data to export: inventory|makers|metrics"
)
OUT_PATH_OPTION = typer.Option(..., "--out", "-o", help="Output file path")
FORMAT_OPTION = typer.Option(
    "json", "--format", "-f", help="Output format: json|csv (default: json)"
)


def _build_client(ctx: typer.Context) -> CoeClient:
    token_getter = get_token_getter(ctx, required=False) or (lambda: "test-token")
    return CoeClient(token_getter)


def _print_json_value(items: Iterable[Mapping[str, Any]]) -> None:
    console.print_json(data={"value": list(items)})


@app.command("inventory")
@handle_cli_errors
def list_inventory(
    ctx: typer.Context,
    environment_id: str | None = ENVIRONMENT_ID_OPTION,
) -> None:
    """List apps and flows across the tenant or a single environment."""

    client = _build_client(ctx)
    items = client.inventory(environment_id=environment_id)
    _print_json_value(items)


@app.command("makers")
@handle_cli_errors
def list_makers(
    ctx: typer.Context,
    environment_id: str | None = ENVIRONMENT_ID_OPTION,
) -> None:
    """List makers (users) contributing apps and flows."""

    client = _build_client(ctx)
    makers = client.makers(environment_id=environment_id)
    _print_json_value(makers)


@app.command("metrics")
@handle_cli_errors
def show_metrics(
    ctx: typer.Context,
    environment_id: str | None = ENVIRONMENT_ID_OPTION,
) -> None:
    """Show summary metrics for apps, flows, and makers."""

    client = _build_client(ctx)
    data = client.metrics(environment_id=environment_id)
    console.print_json(data=data)


@app.command("export")
@handle_cli_errors
def export_data(
    ctx: typer.Context,
    resource: str = RESOURCE_OPTION,
    out: Path = OUT_PATH_OPTION,
    format: str = FORMAT_OPTION,
    environment_id: str | None = ENVIRONMENT_ID_OPTION,
) -> None:
    """Export CoE data to JSON or CSV files."""

    fmt = format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("--format must be one of: json, csv")

    client = _build_client(ctx)
    data: Any
    if resource == "inventory":
        data = client.inventory(environment_id=environment_id)
    elif resource == "makers":
        data = client.makers(environment_id=environment_id)
    elif resource == "metrics":
        data = client.metrics(environment_id=environment_id)
    else:
        raise typer.BadParameter("--resource must be one of: inventory, makers, metrics")

    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        # For parity with other commands, wrap lists in {"value": [...]}.
        if isinstance(data, list):
            payload: Any = {"value": data}
        else:
            payload = data
        out.write_text(json.dumps(payload, indent=2))
        console.print(f"[green]Exported to[/green] {out}")
        return

    # CSV export
    import csv

    with out.open("w", newline="", encoding="utf-8") as fh:
        if isinstance(data, list):
            # Determine columns from union of keys.
            cols: list[str] = []
            for item in data:
                for k in item.keys():
                    if k not in cols:
                        cols.append(k)
            dw = csv.DictWriter(fh, fieldnames=cols)
            dw.writeheader()
            for row in data:
                dw.writerow(row)
        elif isinstance(data, dict):
            # For metrics dict, write key,value CSV.
            cw = csv.writer(fh)
            cw.writerow(["key", "value"])
            for k, v in data.items():
                cw.writerow([k, v])
        else:  # pragma: no cover - defensive fallback
            fh.write("")
    console.print(f"[green]Exported to[/green] {out}")


__all__ = ["app"]
