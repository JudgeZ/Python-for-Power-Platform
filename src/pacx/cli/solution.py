from __future__ import annotations

import base64
import uuid
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click

import typer
from rich import print
from typer.core import TyperGroup

from ..cli_utils import resolve_dataverse_host_from_context
from ..clients.dataverse import DataverseClient
from ..models.dataverse import ExportSolutionRequest, ImportSolutionRequest
from ..solution_source import pack_solution_folder, unpack_solution_zip
from ..solution_sp import pack_from_source, unpack_to_source
from ..errors import PacxError
from .common import get_token_getter, handle_cli_errors

__all__ = [
    "app",
    "LEGACY_ACTIONS",
]

LEGACY_ACTIONS: tuple[str, ...] = (
    "list",
    "export",
    "import",
    "publish-all",
    "pack",
    "unpack",
    "pack-sp",
    "unpack-sp",
)

_legacy_warning_emitted = False


def _emit_legacy_warning() -> None:
    """Emit the compatibility warning exactly once per process."""

    global _legacy_warning_emitted
    if not _legacy_warning_emitted:
        typer.secho(
            "Deprecated: action-style solution invocations are still supported but will be removed. "
            "Use `ppx solution <command>` subcommands.",
            fg="yellow",
        )
        _legacy_warning_emitted = True


class SolutionCommandGroup(TyperGroup):
    """Typer command group that understands the legacy --action shim."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        context_settings = kwargs.setdefault("context_settings", {})
        context_settings.setdefault("allow_extra_args", True)
        context_settings.setdefault("ignore_unknown_options", True)
        super().__init__(*args, **kwargs)
        self.allow_extra_args = True
        self.ignore_unknown_options = True

    def resolve_command(
        self, ctx: click.Context, args: Iterable[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        arguments = list(args)
        action = ctx.params.get("action")
        if action:
            if action not in LEGACY_ACTIONS:
                raise typer.BadParameter(f"Unknown solution action: {action}")
            _emit_legacy_warning()
            arguments = [action, *arguments]
        if arguments:
            first = arguments[0]
            if first == "--action":
                if len(arguments) < 2:
                    raise typer.BadParameter("--action requires an operation name")
                action = arguments[1]
                if action not in LEGACY_ACTIONS:
                    raise typer.BadParameter(f"Unknown solution action: {action}")
                _emit_legacy_warning()
                arguments = [action, *arguments[2:]]
            elif first in LEGACY_ACTIONS and first not in self.commands:
                _emit_legacy_warning()
        return super().resolve_command(ctx, arguments)

    def invoke(self, ctx: click.Context) -> Any:
        action = ctx.params.get("action")
        if action:
            if action not in LEGACY_ACTIONS:
                raise typer.BadParameter(f"Unknown solution action: {action}")
            _emit_legacy_warning()
            command = self.get_command(ctx, action)
            if command is None:
                raise typer.BadParameter(f"Unknown solution action: {action}")
            extras = _gather_legacy_args(ctx)
            command_ctx = command.make_context(
                f"{ctx.info_name} {action}",
                extras,
                parent=ctx,
                resilient_parsing=False,
            )
            try:
                result = command.invoke(command_ctx)
            finally:
                command_ctx.close()
            ctx.exit(result or 0)
        return super().invoke(ctx)


def _gather_legacy_args(ctx: click.Context) -> list[str]:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*protected_args.*",
            category=DeprecationWarning,
        )
        protected = list(getattr(ctx, "protected_args", ()))
    return [*protected, *ctx.args]


def _get_dataverse_client(
    ctx: typer.Context,
    host: str | None,
) -> DataverseClient:
    token_getter = get_token_getter(ctx)
    resolved_host = resolve_dataverse_host_from_context(ctx, host)
    return DataverseClient(token_getter, host=resolved_host)


app = typer.Typer(
    help=(
        "Perform solution lifecycle operations.\n\n"
        "All solution commands accept --host (defaults to profile or DATAVERSE_HOST). "
        "Use `export` with --managed (default: unmanaged) to produce managed packages."
    ),
    cls=SolutionCommandGroup,
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)


@app.callback()
def handle_legacy_invocation(
    ctx: typer.Context,
    action: str | None = typer.Option(
        None,
        "--action",
        help="Deprecated action selector (use subcommands instead)",
        hidden=True,
    ),
) -> None:
    if action:
        if action not in LEGACY_ACTIONS:
            raise typer.BadParameter(f"Unknown solution action: {action}")
        return

    if ctx.invoked_subcommand is None and ctx.args:
        first = ctx.args[0]
        command_group = ctx.command if isinstance(ctx.command, SolutionCommandGroup) else None
        if command_group and first in LEGACY_ACTIONS and first not in command_group.commands:
            _emit_legacy_warning()
            command = command_group.get_command(ctx, first)
            if command is None:
                raise typer.BadParameter(f"Unknown solution action: {first}")
            remaining = list(ctx.args[1:])
            result = command.main(
                args=remaining,
                prog_name=f"{ctx.info_name} {first}",
                standalone_mode=False,
            )
            raise typer.Exit(result or 0)


@app.command("list")
@handle_cli_errors
def list_solutions(
    ctx: typer.Context,
    host: str | None = typer.Option(
        None, "--host", help="Dataverse host (defaults to profile or DATAVERSE_HOST)"
    ),
) -> None:
    """List installed Dataverse solutions."""

    client = _get_dataverse_client(ctx, host)
    solutions = client.list_solutions(select="uniquename,friendlyname,version")
    for solution in solutions:
        print(f"[bold]{solution.uniquename}[/bold]  {solution.friendlyname}  v{solution.version}")


@app.command("export")
@handle_cli_errors
def export_solution(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Solution unique name to export"),
    host: str | None = typer.Option(
        None, "--host", help="Dataverse host (defaults to profile or DATAVERSE_HOST)"
    ),
    managed: bool = typer.Option(
        False, "--managed", help="Export managed solution (default: unmanaged)"
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Output path for the exported solution zip"
    ),
    file: Path | None = typer.Option(
        None,
        "--file",
        help="Legacy alias for --out",
        hidden=True,
    ),
) -> None:
    """Export a solution to a zip archive."""

    client = _get_dataverse_client(ctx, host)
    request = ExportSolutionRequest(SolutionName=name, Managed=managed)
    data = client.export_solution(request)
    output_path = Path(out or file or Path(f"{name}.zip"))
    output_path.write_bytes(data)
    print(f"Exported to {output_path}")


@app.command("import")
@handle_cli_errors
def import_solution(
    ctx: typer.Context,
    file: Path = typer.Option(..., "--file", help="Solution zip to import"),
    host: str | None = typer.Option(
        None, "--host", help="Dataverse host (defaults to profile or DATAVERSE_HOST)"
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Wait for import completion (default: return immediately)"
    ),
    import_job_id: str | None = typer.Option(
        None,
        "--import-job-id",
        help="Reuse or provide ImportJobId (default: generated server-side)",
    ),
) -> None:
    """Import a solution zip into Dataverse."""

    client = _get_dataverse_client(ctx, host)
    payload = base64.b64encode(file.read_bytes()).decode("ascii")
    job_id = import_job_id or uuid.uuid4().hex
    request = ImportSolutionRequest(CustomizationFile=payload, ImportJobId=job_id)
    client.import_solution(request)
    print(f"Import submitted (job: {job_id})")
    if wait:
        try:
            status = client.wait_for_import_job(job_id, interval=1.0, timeout=600.0)
        except TimeoutError as exc:
            message = f"Import job {job_id} did not complete within 600 seconds"
            last_status = getattr(exc, "last_status", None)
            if last_status:
                message = f"{message}; last status: {last_status}"
            raise PacxError(message) from exc
        print(status)


@app.command("publish-all")
@handle_cli_errors
def publish_all(
    ctx: typer.Context,
    host: str | None = typer.Option(
        None, "--host", help="Dataverse host (defaults to profile or DATAVERSE_HOST)"
    ),
) -> None:
    """Publish all Dataverse customizations."""

    client = _get_dataverse_client(ctx, host)
    client.publish_all()
    print("Published all customizations")


@app.command("pack")
@handle_cli_errors
def pack_solution(
    src: Path = typer.Option(..., "--src", help="Folder containing unpacked solution"),
    out: Path | None = typer.Option(
        None, "--out", help="Destination zip path (default: solution.zip)"
    ),
    file: Path | None = typer.Option(
        None,
        "--file",
        help="Legacy alias for --out",
        hidden=True,
    ),
) -> None:
    """Pack an unpacked solution folder into a zip archive."""

    output_path = Path(out or file or Path("solution.zip"))
    pack_solution_folder(str(src), str(output_path))
    print(f"Packed {src} -> {output_path}")


@app.command("unpack")
@handle_cli_errors
def unpack_solution(
    file: Path = typer.Option(..., "--file", help="Solution zip to unpack"),
    out: Path | None = typer.Option(
        None, "--out", help="Destination folder (default: solution_unpacked)"
    ),
) -> None:
    """Unpack a Dataverse solution zip into a folder."""

    output_dir = Path(out or Path("solution_unpacked"))
    unpack_solution_zip(str(file), str(output_dir))
    print(f"Unpacked {file} -> {output_dir}")


@app.command("pack-sp")
@handle_cli_errors
def pack_solution_packager(
    src: Path = typer.Option(..., "--src", help="SolutionPackager source folder"),
    out: Path | None = typer.Option(
        None, "--out", help="Destination zip path (default: solution.zip)"
    ),
    file: Path | None = typer.Option(
        None,
        "--file",
        help="Legacy alias for --out",
        hidden=True,
    ),
) -> None:
    """Pack a SolutionPackager-style tree into a solution zip."""

    output_path = Path(out or file or Path("solution.zip"))
    pack_from_source(str(src), str(output_path))
    print(f"Packed (SolutionPackager-like) {src} -> {output_path}")


@app.command("unpack-sp")
@handle_cli_errors
def unpack_solution_packager(
    file: Path = typer.Option(..., "--file", help="Solution zip to unpack"),
    out: Path | None = typer.Option(
        None, "--out", help="Destination folder (default: solution_src)"
    ),
) -> None:
    """Unpack a solution zip into a SolutionPackager-compatible tree."""

    output_dir = Path(out or Path("solution_src"))
    unpack_to_source(str(file), str(output_dir))
    print(f"Unpacked (SolutionPackager-like) {file} -> {output_dir}")
