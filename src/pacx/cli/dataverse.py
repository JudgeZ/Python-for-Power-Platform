from __future__ import annotations

import json

import typer
from rich import print

from ..bulk_csv import bulk_csv_upsert
from ..clients.dataverse import DataverseClient
from ..cli_utils import resolve_dataverse_host_from_context
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Dataverse operations")


@app.command("whoami")
@handle_cli_errors
def dv_whoami(
    ctx: typer.Context,
    host: str | None = typer.Option(None, help="Dataverse host (else config/env)"),
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    print(dv.whoami())


@app.command("list")
@handle_cli_errors
def dv_list(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    select: str | None = None,
    filter: str | None = None,
    top: int | None = None,
    orderby: str | None = None,
    host: str | None = None,
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    print(dv.list_records(entityset, select=select, filter=filter, top=top, orderby=orderby))


@app.command("get")
@handle_cli_errors
def dv_get(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    record_id: str = typer.Argument(...),
    host: str | None = None,
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    print(dv.get_record(entityset, record_id))


@app.command("create")
@handle_cli_errors
def dv_create(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    data: str = typer.Option(..., help="JSON object string"),
    host: str | None = None,
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    obj = json.loads(data)
    print(dv.create_record(entityset, obj))


@app.command("update")
@handle_cli_errors
def dv_update(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    record_id: str = typer.Argument(...),
    data: str = typer.Option(..., help="JSON object string"),
    host: str | None = None,
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    obj = json.loads(data)
    dv.update_record(entityset, record_id, obj)
    print("updated")


@app.command("delete")
@handle_cli_errors
def dv_delete(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    record_id: str = typer.Argument(...),
    host: str | None = None,
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    dv.delete_record(entityset, record_id)
    print("deleted")


@app.command("bulk-csv")
@handle_cli_errors
def dv_bulk_csv(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    csv_path: str = typer.Argument(...),
    id_column: str = typer.Option(..., help="Column containing record id for PATCH; blank -> POST"),
    key_columns: str = typer.Option(
        "", help="Comma-separated alternate key columns for PATCH when id is blank"
    ),
    create_if_missing: bool = typer.Option(
        True, help="POST when id and key columns are not present"
    ),
    host: str | None = None,
    chunk_size: int = typer.Option(50, help="Records per $batch"),
    report: str | None = typer.Option(None, help="Write per-op results CSV to this path"),
):
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    dv = DataverseClient(token_getter, host=resolved_host)
    keys = [s.strip() for s in (key_columns or "").split(",") if s.strip()]
    result = bulk_csv_upsert(
        dv,
        entityset,
        csv_path,
        id_column,
        key_columns=keys or None,
        chunk_size=chunk_size,
        create_if_missing=create_if_missing,
    )
    if report:
        import csv as _csv

        with open(report, "w", newline="", encoding="utf-8") as handle:
            writer = _csv.writer(handle)
            writer.writerow(["row_index", "content_id", "status_code", "reason", "json"])
            for row in result.operations:
                writer.writerow(
                    [
                        row.get("row_index"),
                        row.get("content_id"),
                        row.get("status_code"),
                        row.get("reason"),
                        (row.get("json") or ""),
                    ]
                )
        print(f"Wrote per-op report to {report}")
    stats = result.stats
    print(
        "Bulk upsert completed: "
        f"{stats['successes']} succeeded, {stats['failures']} failed, "
        f"retries={stats['retry_invocations']}"
    )


__all__ = [
    "app",
    "dv_whoami",
    "dv_list",
    "dv_get",
    "dv_create",
    "dv_update",
    "dv_delete",
    "dv_bulk_csv",
]
