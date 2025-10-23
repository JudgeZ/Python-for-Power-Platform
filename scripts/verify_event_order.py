"""Check the order and structure of filesystem replay YAML files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pacx.filesystem.replay import ReplayFileReport, verify_replay_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="Directory containing replay YAML files")
    return parser


def _format_report(report: ReplayFileReport) -> str:
    display_path = report.path.as_posix()
    if report.ok:
        return f"OK ✓ {display_path}"  # noqa: T201
    code = report.error_code or 1
    return f"ERROR ({code}) {display_path}: {report.message}"  # noqa: T201


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    directory = Path(args.directory)
    reports = verify_replay_directory(directory)

    exit_code = 0
    for report in reports:
        print(_format_report(report))
        if not report.ok:
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

