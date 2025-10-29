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
from ..errors import PacxError
from ..models.dataverse import ExportSolutionRequest, ImportSolutionRequest
from ..solution_source import pack_solution_folder, unpack_solution_zip
from ..solution_sp import pack_from_source, unpack_to_source
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


PACK_SRC_OPTION = typer.Option(..., "--src", help="SolutionPackager source folder")
PACK_OUT_OPTION = typer.Option(None, "--out", help="Destination zip path (default: solution.zip)")
PACK_FILE_ALIAS_OPTION = typer.Option(
    None,
    "--file",
    help="Legacy alias for --out",
    hidden=True,
)
UNPACK_FILE_OPTION = typer.Option(..., "--file", help="Solution zip to unpack")
UNPACK_OUT_OPTION = typer.Option(None, "--out", help="Destination folder (default: solution_src)")
HOST_OPTION = typer.Option(
    None, "--host", help="Dataverse host (defaults to profile or DATAVERSE_HOST)"
)
EXPORT_NAME_OPTION = typer.Option(..., "--name", "-n", help="Solution unique name to export")
EXPORT_MANAGED_OPTION = typer.Option(
    False, "--managed", help="Export managed solution (default: unmanaged)"
)
EXPORT_INCLUDE_DEPS_OPTION = typer.Option(
    False, "--include-dependencies", help="Include solution dependencies where supported"
)
EXPORT_OUT_OPTION = typer.Option(None, "--out", help="Output path for the exported solution zip")
EXPORT_FILE_ALIAS_OPTION = typer.Option(
    None,
    "--file",
    help="Legacy alias for --out",
    hidden=True,
)
IMPORT_FILE_OPTION = typer.Option(..., "--file", help="Solution zip to import")
WAIT_OPTION = typer.Option(
    False, "--wait", help="Wait for import completion (default: return immediately)"
)
IMPORT_JOB_ID_OPTION = typer.Option(
    None,
    "--import-job-id",
    help="Reuse or provide ImportJobId (default: generated server-side)",
)
PACK_SRC_MAIN_OPTION = typer.Option(..., "--src", help="Folder containing unpacked solution")
PACK_OUT_MAIN_OPTION = typer.Option(
    None, "--out", help="Destination zip path (default: solution.zip)"
)
PACK_FILE_MAIN_OPTION = typer.Option(
    None,
    "--file",
    help="Legacy alias for --out",
    hidden=True,
)
UNPACK_FILE_MAIN_OPTION = typer.Option(..., "--file", help="Solution zip to unpack")
UNPACK_OUT_MAIN_OPTION = typer.Option(
    None, "--out", help="Destination folder (default: solution_unpacked)"
)


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
    host: str | None = HOST_OPTION,
) -> None:
    """List installed Dataverse solutions."""

    client = _get_dataverse_client(ctx, host)
    solutions = client.list_solutions(select="uniquename,friendlyname,version")
    for solution in solutions:
        print(f"[bold]{solution.uniquename}[/bold]  {solution.friendlyname}  v{solution.version}")


@app.command("deps")
@handle_cli_errors
def solution_dependencies(
    ctx: typer.Context,
    name: str = EXPORT_NAME_OPTION,
    host: str | None = HOST_OPTION,
    format: str = typer.Option("json", "--format", help="Output format: json|dot"),
) -> None:
    """Print the dependency graph for a solution.

    JSON is the default; use ``--format dot`` to emit a Graphviz DOT graph.
    """

    client = _get_dataverse_client(ctx, host)
    deps = client.get_solution_dependencies(name)
    fmt = format.lower()
    if fmt == "dot":

        def _node(n: dict[str, Any], role: str) -> str:
            for key in (f"{role}componentname", f"{role}componentlogicalname"):
                v = n.get(key)
                if isinstance(v, str) and v:
                    return v
            for key in (f"{role}componentobjectid",):
                v = n.get(key)
                if isinstance(v, str) and v:
                    return v
            return role

        lines = ["digraph dependencies {"]
        for d in deps:
            a = _node(d, "dependent")
            b = _node(d, "required")
            lines.append(f'  "{a}" -> "{b}";')
        lines.append("}")
        print("\n".join(lines))
    else:
        print({"value": deps})


@app.command("components")
@handle_cli_errors
def solution_components(
    ctx: typer.Context,
    name: str = EXPORT_NAME_OPTION,
    host: str | None = HOST_OPTION,
    type: int | None = typer.Option(None, "--type", help="Filter by component type id"),
    format: str = typer.Option("json", "--format", help="Output format: json|csv"),
) -> None:
    """List components for a solution."""

    client = _get_dataverse_client(ctx, host)
    comps = client.get_solution_components(name, component_type=type)
    if format.lower() == "csv":
        import csv as _csv  # local import to avoid hard dep for non-csv users
        import io

        if not comps:
            print("")
            return
        header = sorted({k for row in comps for k in row.keys()})
        buf = io.StringIO()
        writer = _csv.DictWriter(buf, fieldnames=header)
        writer.writeheader()
        for row in comps:
            writer.writerow({k: row.get(k, "") for k in header})
        print(buf.getvalue().rstrip("\n"))
    else:
        print({"value": comps})


@app.command("check")
@handle_cli_errors
def solution_check(
    ctx: typer.Context,
    name: str = EXPORT_NAME_OPTION,
    host: str | None = HOST_OPTION,
) -> None:
    """Validate that dependencies for a solution appear satisfied.

    This is a lightweight heuristic that flags entries where a ``missing`` field
    is present and truthy in the dependency payload.
    """

    client = _get_dataverse_client(ctx, host)
    deps = client.get_solution_dependencies(name)
    missing = [d for d in deps if bool(str(d.get("missing", "")).lower() in {"true", "1"})]
    if missing:
        print({"ok": False, "missing": missing})
        raise typer.Exit(code=1)
    print({"ok": True, "count": len(deps)})


@app.command("export")
@handle_cli_errors
def export_solution(
    ctx: typer.Context,
    name: str = EXPORT_NAME_OPTION,
    host: str | None = HOST_OPTION,
    managed: bool = EXPORT_MANAGED_OPTION,
    include_dependencies: bool = EXPORT_INCLUDE_DEPS_OPTION,
    out: Path | None = EXPORT_OUT_OPTION,
    file: Path | None = EXPORT_FILE_ALIAS_OPTION,
) -> None:
    """Export a solution to a zip archive."""

    client = _get_dataverse_client(ctx, host)
    request = ExportSolutionRequest(
        SolutionName=name,
        Managed=managed,
        IncludeSolutionDependencies=True if include_dependencies else None,
    )
    data = client.export_solution(request)
    output_path = Path(out or file or Path(f"{name}.zip"))
    output_path.write_bytes(data)
    print(f"Exported to {output_path}")


@app.command("import")
@handle_cli_errors
def import_solution(
    ctx: typer.Context,
    file: Path = IMPORT_FILE_OPTION,
    host: str | None = HOST_OPTION,
    wait: bool = WAIT_OPTION,
    import_job_id: str | None = IMPORT_JOB_ID_OPTION,
    activate_plugins: bool = typer.Option(
        False, "--activate-plugins", help="Activate plug-ins after import"
    ),
    publish_workflows: bool = typer.Option(
        False, "--publish-workflows", help="Publish workflows after import"
    ),
    overwrite_unmanaged: bool = typer.Option(
        False, "--overwrite-unmanaged", help="Overwrite unmanaged customizations"
    ),
) -> None:
    """Import a solution zip into Dataverse."""

    client = _get_dataverse_client(ctx, host)
    payload = base64.b64encode(file.read_bytes()).decode("ascii")
    job_id = import_job_id or uuid.uuid4().hex
    request_args: dict[str, object] = {
        "CustomizationFile": payload,
        "ImportJobId": job_id,
    }
    if activate_plugins:
        request_args["ActivatePlugins"] = True
    if publish_workflows:
        request_args["PublishWorkflows"] = True
    if overwrite_unmanaged:
        request_args["OverwriteUnmanagedCustomizations"] = True

    request = ImportSolutionRequest(**request_args)
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
    host: str | None = HOST_OPTION,
) -> None:
    """Publish all Dataverse customizations."""

    client = _get_dataverse_client(ctx, host)
    client.publish_all()
    print("Published all customizations")


@app.command("pack")
@handle_cli_errors
def pack_solution(
    src: Path = PACK_SRC_MAIN_OPTION,
    out: Path | None = PACK_OUT_MAIN_OPTION,
    file: Path | None = PACK_FILE_MAIN_OPTION,
) -> None:
    """Pack an unpacked solution folder into a zip archive."""

    output_path = Path(out or file or Path("solution.zip"))
    pack_solution_folder(str(src), str(output_path))
    print(f"Packed {src} -> {output_path}")


@app.command("unpack")
@handle_cli_errors
def unpack_solution(
    file: Path = UNPACK_FILE_MAIN_OPTION,
    out: Path | None = UNPACK_OUT_MAIN_OPTION,
) -> None:
    """Unpack a Dataverse solution zip into a folder."""

    output_dir = Path(out or Path("solution_unpacked"))
    unpack_solution_zip(str(file), str(output_dir))
    print(f"Unpacked {file} -> {output_dir}")


@app.command("pack-sp")
@handle_cli_errors
def pack_solution_packager(
    src: Path = PACK_SRC_OPTION,
    out: Path | None = PACK_OUT_OPTION,
    file: Path | None = PACK_FILE_ALIAS_OPTION,
) -> None:
    """Pack a SolutionPackager-style tree into a solution zip."""

    output_path = Path(out or file or Path("solution.zip"))
    pack_from_source(str(src), str(output_path))
    print(f"Packed (SolutionPackager-like) {src} -> {output_path}")


@app.command("unpack-sp")
@handle_cli_errors
def unpack_solution_packager(
    file: Path = UNPACK_FILE_OPTION,
    out: Path | None = UNPACK_OUT_OPTION,
) -> None:
    """Unpack a solution zip into a SolutionPackager-compatible tree."""

    output_dir = Path(out or Path("solution_src"))
    unpack_to_source(str(file), str(output_dir))
    print(f"Unpacked (SolutionPackager-like) {file} -> {output_dir}")
