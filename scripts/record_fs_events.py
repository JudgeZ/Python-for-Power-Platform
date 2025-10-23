"""Generate filesystem replay YAML files from a declarative configuration."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pacx.filesystem.replay import load_replay_config, write_replay_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to the replay configuration YAML file")
    parser.add_argument(
        "--replay-dir",
        required=True,
        help="Directory where the generated replay YAML files should be written",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    replay_dir = Path(args.replay_dir)

    replays = load_replay_config(config_path)
    written_paths = write_replay_files(replays, replay_dir)

    for path in written_paths:
        print(f"Wrote {path}")  # noqa: T201 - CLI utility output

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

