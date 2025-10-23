"""Tests for filesystem replay helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pacx.filesystem.replay import (
    ReplayConfigError,
    load_replay_config,
    verify_replay_directory,
    write_replay_files,
)


def _write_config(path: Path) -> None:
    payload = {
        "replays": [
            {
                "name": "alpha",
                "description": "Example replay with timestamps",
                "events": [
                    {
                        "operation": "create",
                        "path": "src/file.txt",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "checksum": "aaa",
                    },
                    {
                        "operation": "modify",
                        "path": "src/file.txt",
                        "timestamp": "2024-01-01T00:00:05Z",
                        "checksum": "bbb",
                    },
                ],
            },
            {
                "name": "beta",
                "description": "Replay without timestamps",
                "events": [
                    {
                        "operation": "delete",
                        "path": "src/old.txt",
                    }
                ],
            },
        ]
    }
    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(payload, stream)


def test_write_and_verify_replays(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)

    replays = load_replay_config(config_path)
    output_dir = tmp_path / "replays"
    written_paths = write_replay_files(replays, output_dir)

    assert {path.name for path in written_paths} == {"alpha.yaml", "beta.yaml"}

    alpha_doc = yaml.safe_load((output_dir / "alpha.yaml").read_text(encoding="utf-8"))
    assert alpha_doc["events"][0]["sequence"] == 1
    assert alpha_doc["events"][1]["sequence"] == 2
    assert alpha_doc["events"][0]["checksum"] == "aaa"

    beta_doc = yaml.safe_load((output_dir / "beta.yaml").read_text(encoding="utf-8"))
    assert beta_doc["events"] == [
        {
            "sequence": 1,
            "operation": "delete",
            "path": "src/old.txt",
        }
    ]

    reports = verify_replay_directory(output_dir)
    assert all(report.ok for report in reports)


def test_verify_replay_directory_detects_bad_root(tmp_path: Path) -> None:
    broken_file = tmp_path / "broken.yaml"
    broken_file.write_text("- just\n- a\n- list\n", encoding="utf-8")

    reports = verify_replay_directory(tmp_path)
    assert len(reports) == 1
    report = reports[0]
    assert not report.ok
    assert report.error_code == 2
    assert "mapping" in report.message


def test_load_replay_config_rejects_invalid_event(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    payload = {
        "replays": [
            {
                "name": "oops",
                "description": None,
                "events": ["not-a-mapping"],
            }
        ]
    }
    with config_path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(payload, stream)

    with pytest.raises(ReplayConfigError):
        load_replay_config(config_path)

