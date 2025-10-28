"""Typer-based OpenAPI validation CLI used by local tooling and CI."""

from __future__ import annotations

import json
import shlex
import shutil
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import typer

from ._shared import ExitCode, Settings, get_logger, run_command

LOGGER = get_logger(__name__)


try:  # Optional prettified console output.
    from rich.console import Console
    from rich.table import Table

    _CONSOLE: Console | None = Console()
except ImportError:  # pragma: no cover - dependency optional.
    _CONSOLE = None

yaml: Any | None

try:
    yaml = import_module("yaml")
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

ValidateSpec = Callable[[dict[str, Any]], None]
try:
    validator_module = import_module("openapi_spec_validator")
    validate_spec = cast(ValidateSpec | None, validator_module.validate_spec)
    exceptions_module = import_module("openapi_spec_validator.exceptions")
    OpenAPISpecValidatorError = cast(
        type[Exception],
        exceptions_module.OpenAPISpecValidatorError,
    )
except ModuleNotFoundError:  # pragma: no cover
    validate_spec = None
    OpenAPISpecValidatorError = Exception


DEFAULT_GLOBS: tuple[str, ...] = (
    "openapi/*.yaml",
    "openapi/*.yml",
)


class DependencyError(RuntimeError):
    """Raised when the CLI cannot satisfy runtime dependencies."""

    def __init__(self, message: str, *, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(slots=True)
class Issue:
    source: str
    level: str
    message: str
    pointer: str | None = None
    rule: str | None = None


@dataclass(slots=True)
class FileReport:
    path: Path
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    infos: list[Issue] = field(default_factory=list)
    spectral_skipped: bool = False

    @property
    def failed(self) -> bool:
        return bool(self.errors)

    @property
    def warning_only(self) -> bool:
        return bool(self.warnings) and not self.failed


def _require_dependencies() -> None:
    missing: list[str] = []
    if yaml is None:
        missing.append("PyYAML")
    if validate_spec is None:
        missing.append("openapi-spec-validator")
    if missing:
        packages = ", ".join(missing)
        raise DependencyError(
            f"Missing runtime dependency: {packages}. Install pacx[dev] to proceed.",
            exit_code=ExitCode.MISSING_DEPENDENCY,
        )


def _split_patterns(raw: str) -> tuple[str, ...]:
    return tuple(pattern.strip() for pattern in raw.split(",") if pattern.strip())


def _discover_files(files: Iterable[Path] | None, settings: Settings) -> list[Path]:
    if files:
        resolved = [path.resolve() for path in files]
        missing = [str(path) for path in resolved if not path.is_file()]
        if missing:
            raise DependencyError(
                f"File(s) not found: {', '.join(missing)}",
                exit_code=ExitCode.FAILURE,
            )
        return resolved

    patterns = _split_patterns(settings.openapi_glob) or list(DEFAULT_GLOBS)
    discovered: dict[Path, None] = {}
    for pattern in patterns:
        for candidate in Path().glob(pattern):
            if candidate.is_file():
                discovered[candidate.resolve()] = None
    return sorted(discovered.keys())


def _load_yaml(path: Path) -> tuple[dict, list[Issue]]:
    issues: list[Issue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(Issue("filesystem", "error", f"Unable to read file: {exc}"))
        return {}, issues

    if yaml is None:  # pragma: no cover - validated by _require_dependencies
        raise DependencyError(
            "PyYAML is required to parse OpenAPI documents.",
            exit_code=ExitCode.MISSING_DEPENDENCY,
        )
    try:
        data = yaml.safe_load(text)
    except Exception as exc:
        issues.append(Issue("yaml", "error", f"YAML parsing failed: {exc}"))
        return {}, issues

    if not isinstance(data, dict):
        issues.append(Issue("yaml", "error", "Top-level document must be a mapping."))
        return {}, issues
    return data, issues


def _validate_openapi(data: dict) -> list[Issue]:
    if validate_spec is None:  # pragma: no cover - validated by _require_dependencies
        raise DependencyError(
            "openapi-spec-validator is required for validation.",
            exit_code=ExitCode.MISSING_DEPENDENCY,
        )
    issues: list[Issue] = []
    try:
        validate_spec(data)
    except OpenAPISpecValidatorError as exc:
        issues.append(Issue("openapi", "error", str(exc)))
    except Exception as exc:  # pragma: no cover - defensive fallback
        issues.append(Issue("openapi", "error", f"Unexpected validator error: {exc}"))
    return issues


def _resolved_spectral(command_override: str | None, settings: Settings) -> list[str] | None:
    if command_override is not None and not command_override.strip():
        return None

    raw = command_override or settings.spectral_cmd
    tokens = shlex.split(raw)
    if not tokens:
        return None
    if shutil.which(tokens[0]) is None:
        if command_override is None:
            LOGGER.warning("Spectral command '%s' not found; skipping lint.", tokens[0])
            return None
        raise DependencyError(
            f"Spectral command '{tokens[0]}' not available on PATH.",
            exit_code=ExitCode.MISSING_DEPENDENCY,
        )
    return tokens


def _run_spectral(path: Path, base_cmd: list[str]) -> tuple[list[Issue], list[Issue], list[Issue]]:
    cmd = [*base_cmd, "--format", "json", "--quiet", str(path)]
    process = run_command(cmd)
    stdout = process.stdout.strip()
    if process.returncode not in (0, 1):  # Spectral uses 1 for lint failures.
        message = process.stderr.strip() or stdout or "Spectral invocation failed."
        raise DependencyError(message, exit_code=ExitCode.FAILURE)
    if not stdout:
        return [], [], []

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise DependencyError(
            f"Spectral returned non-JSON output: {exc}", exit_code=ExitCode.FAILURE
        ) from exc

    severity_map = {
        0: "error",
        1: "warning",
        2: "info",
        3: "hint",
        "error": "error",
        "warning": "warning",
        "warn": "warning",
        "info": "info",
        "hint": "hint",
    }

    errors: list[Issue] = []
    warnings: list[Issue] = []
    infos: list[Issue] = []
    for entry in payload:
        severity = severity_map.get(entry.get("severity", "warning"), "warning")
        issue = Issue(
            source="spectral",
            level=severity,
            message=entry.get("message", "Spectral issue"),
            pointer="/".join(str(part) for part in entry.get("path", [])) or None,
            rule=entry.get("code"),
        )
        if severity == "error":
            errors.append(issue)
        elif severity == "warning":
            warnings.append(issue)
        else:
            infos.append(issue)
    return errors, warnings, infos


def _validate_one(path: Path, spectral_cmd: list[str] | None) -> FileReport:
    payload, issues = _load_yaml(path)
    report = FileReport(path=path)
    report.errors.extend(issues)
    if report.errors:
        return report

    report.errors.extend(_validate_openapi(payload))

    if spectral_cmd is None:
        report.spectral_skipped = True
        return report

    errors, warnings, infos = _run_spectral(path, spectral_cmd)
    report.errors.extend(errors)
    report.warnings.extend(warnings)
    report.infos.extend(infos)
    return report


def _validate_files(
    files: Sequence[Path],
    *,
    spectral_cmd: list[str] | None,
    concurrency: int,
) -> list[FileReport]:
    if not files:
        return []
    if concurrency <= 1 or len(files) == 1:
        return [_validate_one(path, spectral_cmd) for path in files]

    reports: list[FileReport] = []
    with ThreadPoolExecutor(max_workers=min(concurrency, len(files))) as executor:
        futures = {executor.submit(_validate_one, path, spectral_cmd): path for path in files}
        for future in as_completed(futures):
            reports.append(future.result())
    reports.sort(key=lambda report: str(report.path))
    return reports


def _render_console(reports: Sequence[FileReport], *, strict: bool) -> None:
    if _CONSOLE is None:
        for report in reports:
            state = "failed" if report.failed else "warning" if report.warning_only else "passed"
            typer.echo(
                f"{report.path}: {state} (errors={len(report.errors)}, warnings={len(report.warnings)})"
            )
            if report.spectral_skipped:
                typer.echo("  note: spectral skipped")
        return

    table = Table(title="OpenAPI validation summary")
    table.add_column("File")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Notes")
    for report in reports:
        if report.failed or (strict and report.warning_only):
            status = "[red]failed[/red]"
        elif report.warning_only:
            status = "[yellow]warning[/yellow]"
        else:
            status = "[green]passed[/green]"
        note = "spectral skipped" if report.spectral_skipped else ""
        table.add_row(
            f"{status} {report.path}",
            str(len(report.errors)),
            str(len(report.warnings)),
            note,
        )
    _CONSOLE.print(table)


def _write_json_report(path: Path, reports: Sequence[FileReport], *, strict: bool) -> None:
    summary = {
        "files": len(reports),
        "failures": sum(1 for item in reports if item.failed or (strict and item.warning_only)),
        "warnings": sum(1 for item in reports if item.warning_only),
    }
    payload = {
        "summary": summary,
        "strict": strict,
        "files": [
            {
                "path": str(item.path),
                "errors": [asdict(issue) for issue in item.errors],
                "warnings": [asdict(issue) for issue in item.warnings],
                "infos": [asdict(issue) for issue in item.infos],
                "spectralSkipped": item.spectral_skipped,
            }
            for item in reports
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _resolve_concurrency(requested: int | None, default: int, total: int) -> int:
    if total <= 1:
        return 1
    if requested is None or requested < 1:
        return max(1, min(default, total))
    return min(requested, total)


app = typer.Typer(add_completion=False)


@app.command()
def validate(
    files: list[Path] | None = typer.Option(  # noqa: B008
        None,
        "--file",
        "-f",
        help="Explicit OpenAPI specification to validate. May be repeated.",
    ),
    json_report: Path | None = typer.Option(  # noqa: B008
        None,
        "--json-report",
        help="Optional path to write a JSON summary report.",
    ),
    spectral_cmd: str | None = typer.Option(  # noqa: B008
        None,
        "--spectral-cmd",
        help="Override the Spectral command (default: settings or env). Empty string skips Spectral.",
    ),
    strict: bool = typer.Option(  # noqa: B008
        False,
        "--strict",
        help="Treat Spectral warnings as failures.",
    ),
    concurrency: int | None = typer.Option(  # noqa: B008
        None,
        "--concurrency",
        "-j",
        min=1,
        help="Number of worker threads (default: settings).",
    ),
) -> None:
    """Validate OpenAPI documents with schema checks and Spectral linting."""

    try:
        _require_dependencies()
    except DependencyError as exc:
        raise typer.Exit(exc.exit_code) from exc

    settings = Settings()
    try:
        targets = _discover_files(files, settings)
    except DependencyError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(exc.exit_code) from exc

    if not targets:
        typer.echo("No OpenAPI specifications discovered; skipping validation.")
        raise typer.Exit(ExitCode.SUCCESS)

    try:
        spectral_tokens = _resolved_spectral(spectral_cmd, settings)
    except DependencyError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(exc.exit_code) from exc

    worker_count = _resolve_concurrency(concurrency, settings.concurrency, len(targets))
    try:
        reports = _validate_files(
            targets,
            spectral_cmd=spectral_tokens,
            concurrency=worker_count,
        )
    except DependencyError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(exc.exit_code) from exc

    reports.sort(key=lambda report: str(report.path))
    _render_console(reports, strict=strict)

    if json_report:
        _write_json_report(json_report, reports, strict=strict)

    failures = sum(1 for report in reports if report.failed or (strict and report.warning_only))
    if failures:
        raise typer.Exit(ExitCode.FAILURE)
    raise typer.Exit(ExitCode.SUCCESS)


def main() -> None:
    """Entry-point for ``python -m scripts.openapi_validate``."""

    app()


if __name__ == "__main__":
    main()
