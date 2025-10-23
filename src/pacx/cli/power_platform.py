from __future__ import annotations

import base64

import typer
from rich import print

from ..cli_utils import resolve_dataverse_host_from_context, resolve_environment_id_from_context
from ..clients.dataverse import DataverseClient
from ..clients.power_platform import PowerPlatformClient
from ..models.dataverse import ExportSolutionRequest, ImportSolutionRequest
from ..solution_sp import pack_from_source, unpack_to_source
from .common import get_token_getter, handle_cli_errors


def register(app: typer.Typer) -> None:
    app.command("env")(list_envs)
    app.command("apps")(list_apps)
    app.command("flows")(list_flows)
    app.command("solution")(solution_cmd)


@handle_cli_errors
def list_envs(
    ctx: typer.Context,
    api_version: str = typer.Option("2022-03-01-preview", help="Power Platform API version"),
):
    """List Power Platform environments."""
    token_getter = get_token_getter(ctx)
    client = PowerPlatformClient(token_getter, api_version=api_version)
    envs = client.list_environments()
    for env in envs:
        print(f"[bold]{env.name or env.id}[/bold]  type={env.type}  location={env.location}")


@handle_cli_errors
def list_apps(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
    top: int | None = typer.Option(None, help="$top"),
):
    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = PowerPlatformClient(token_getter)
    apps = client.list_apps(environment, top=top)
    for app_summary in apps:
        print(f"[bold]{app_summary.name or app_summary.id}[/bold]")


@handle_cli_errors
def list_flows(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
):
    token_getter = get_token_getter(ctx)
    environment = resolve_environment_id_from_context(ctx, environment_id)
    client = PowerPlatformClient(token_getter)
    flows = client.list_cloud_flows(environment)
    for flow in flows:
        print(f"[bold]{flow.name or flow.id}[/bold]")


@handle_cli_errors
def solution_cmd(
    ctx: typer.Context,
    action: str = typer.Argument(
        ..., help="list|export|import|publish-all|pack|unpack|unpack-sp|pack-sp"
    ),
    host: str | None = typer.Option(None, help="Dataverse host (e.g. org.crm.dynamics.com)"),
    name: str | None = typer.Option(None, help="Solution unique name (for export)"),
    managed: bool = typer.Option(False, help="Export as managed"),
    file: str | None = typer.Option(None, help="Path to solution zip (import/export/pack)"),
    src: str | None = typer.Option(None, help="Folder to pack from (pack)"),
    out: str | None = typer.Option(None, help="Output path (export/pack/unpack)"),
    wait: bool = typer.Option(False, help="Wait for long-running operations (import)"),
    import_job_id: str | None = typer.Option(None, help="Provide/track ImportJobId for import"),
):
    from ..solution_source import pack_solution_folder, unpack_solution_zip

    requires_dataverse = action in ("list", "export", "import", "publish-all")
    resolved_host = (
        resolve_dataverse_host_from_context(ctx, host) if requires_dataverse else None
    )
    token_getter = get_token_getter(ctx, required=requires_dataverse)
    if requires_dataverse:
        dv = DataverseClient(token_getter, host=resolved_host)
    else:
        dv = None

    if action == "list":
        assert dv
        solutions = dv.list_solutions(select="uniquename,friendlyname,version")
        for solution in solutions:
            print(f"[bold]{solution.uniquename}[/bold]  {solution.friendlyname}  v{solution.version}")
    elif action == "export":
        if not name:
            raise typer.BadParameter("--name is required for export")
        assert dv
        request = ExportSolutionRequest(SolutionName=name, Managed=managed)
        data = dv.export_solution(request)
        output = out or file or f"{name}.zip"
        with open(output, "wb") as handle:
            handle.write(data)
        print(f"Exported to {output}")
    elif action == "import":
        if not file:
            raise typer.BadParameter("--file is required for import")
        assert dv
        with open(file, "rb") as handle:
            payload = base64.b64encode(handle.read()).decode("ascii")
        job_id = import_job_id or __import__("uuid").uuid4().hex
        request = ImportSolutionRequest(CustomizationFile=payload, ImportJobId=job_id)
        dv.import_solution(request)
        print(f"Import submitted (job: {job_id})")
        if wait:
            status = dv.wait_for_import_job(job_id, interval=1.0, timeout=600.0)
            print(status)
    elif action == "unpack-sp":
        if not file:
            raise typer.BadParameter("--file required for unpack-sp")
        output = out or "solution_src"
        unpack_to_source(file, output)
        print(f"Unpacked (SolutionPackager-like) {file} -> {output}")
    elif action == "pack-sp":
        if not src:
            raise typer.BadParameter("--src required for pack-sp")
        output = out or file or "solution.zip"
        pack_from_source(src, output)
        print(f"Packed (SolutionPackager-like) {src} -> {output}")
    elif action == "publish-all":
        assert dv
        dv.publish_all()
        print("Published all customizations")
    elif action == "pack":
        if not src:
            raise typer.BadParameter("--src required for pack")
        output = out or file or "solution.zip"
        pack_solution_folder(src, output)
        print(f"Packed {src} -> {output}")
    elif action == "unpack":
        if not file:
            raise typer.BadParameter("--file required for unpack")
        output = out or "solution_unpacked"
        unpack_solution_zip(file, output)
        print(f"Unpacked {file} -> {output}")
    else:
        raise typer.BadParameter("Unknown action")


__all__ = [
    "register",
    "list_envs",
    "list_apps",
    "list_flows",
    "solution_cmd",
]
