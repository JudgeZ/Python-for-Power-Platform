from __future__ import annotations

from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from pacx.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")


def test_copy_environment_waits_and_prints_final_state(respx_mock: Any) -> None:
    env_id = "env-1"
    # Submit copy -> returns operation location
    respx_mock.post(
        f"https://api.powerplatform.com/environmentmanagement/environments/{env_id}:copy"
    ).mock(return_value=httpx.Response(202, headers={"Operation-Location": "/ops/1"}, json={}))
    # Polling sequence: InProgress -> Succeeded
    respx_mock.get("https://api.powerplatform.com/ops/1").mock(
        side_effect=[
            httpx.Response(200, json={"status": "InProgress"}),
            httpx.Response(200, json={"status": "Succeeded"}),
        ]
    )

    # Minimal required fields for EnvironmentCopyRequest
    payload = '{"targetEnvironmentName": "copy-env", "targetEnvironmentRegion": "unitedstates"}'
    result = runner.invoke(
        app,
        [
            "environment",
            "copy",
            env_id,
            "--payload",
            payload,
            "--wait",
            "--timeout",
            "10",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Succeeded" in result.output


def test_backup_timeout_returns_last_state(respx_mock: Any) -> None:
    env_id = "env-2"
    respx_mock.post(
        f"https://api.powerplatform.com/environmentmanagement/environments/{env_id}:backup"
    ).mock(return_value=httpx.Response(202, headers={"Operation-Location": "/ops/2"}, json={}))
    respx_mock.get("https://api.powerplatform.com/ops/2").mock(
        side_effect=[httpx.Response(200, json={"status": "InProgress"})] * 3
    )

    # Minimal required fields for EnvironmentBackupRequest
    payload = '{"label": "Nightly"}'
    result = runner.invoke(
        app,
        [
            "environment",
            "backup",
            env_id,
            "--payload",
            payload,
            "--wait",
            "--timeout",
            "0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "InProgress" in result.output


def test_restore_failure_sets_exit_code(respx_mock: Any) -> None:
    env_id = "env-3"
    respx_mock.post(
        f"https://api.powerplatform.com/environmentmanagement/environments/{env_id}:restore"
    ).mock(return_value=httpx.Response(202, headers={"Operation-Location": "/ops/3"}, json={}))
    respx_mock.get("https://api.powerplatform.com/ops/3").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "Failed",
                "error": {"message": "Restore validation failed."},
            },
        )
    )

    payload = '{"backupId": "backup-1"}'
    result = runner.invoke(
        app,
        [
            "environment",
            "restore",
            env_id,
            "--payload",
            payload,
            "--wait",
            "--timeout",
            "10",
        ],
    )

    assert result.exit_code == 1
    assert "Failed" in result.output
    assert "Restore validation failed." in result.output
