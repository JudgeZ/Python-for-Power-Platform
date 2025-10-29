from __future__ import annotations

import base64
import json as _json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from pacx.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")


def test_export_include_dependencies_flag(respx_mock: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = _json.loads(request.content.decode())
        assert payload["SolutionName"] == "MySolution"
        # When flag is false, field may be omitted; when true, expect True
        assert payload.get("IncludeSolutionDependencies") is True
        return httpx.Response(
            200, json={"ExportSolutionFile": base64.b64encode(b"zip").decode("ascii")}
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ExportSolution").mock(
        side_effect=handler
    )
    out = runner.invoke(
        app, ["solution", "export", "--name", "MySolution", "--include-dependencies"]
    )
    assert out.exit_code == 0, out.output
    assert "Exported to" in out.output


def test_import_defaults_publish_and_overwrite(
    tmp_path: Path, respx_mock: Any
) -> None:
    zip_path = tmp_path / "s.zip"
    zip_path.write_bytes(b"zip")

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = _json.loads(request.content.decode())
        captured.update(body)
        return httpx.Response(202, headers={"Operation-Location": "ops/1"}, json={})

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ImportSolution").mock(
        side_effect=handler
    )
    out = runner.invoke(
        app,
        [
            "solution",
            "import",
            "--file",
            str(zip_path),
        ],
    )
    assert out.exit_code == 0, out.output
    assert captured.get("PublishWorkflows") is True
    assert captured.get("OverwriteUnmanagedCustomizations") is True


def test_import_flags_flow_into_payload(tmp_path: Path, respx_mock: Any) -> None:
    zip_path = tmp_path / "s.zip"
    zip_path.write_bytes(b"zip")

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = _json.loads(request.content.decode())
        captured.update(body)
        return httpx.Response(202, headers={"Operation-Location": "ops/1"}, json={})

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ImportSolution").mock(
        side_effect=handler
    )
    out = runner.invoke(
        app,
        [
            "solution",
            "import",
            "--file",
            str(zip_path),
            "--activate-plugins",
            "--no-publish-workflows",
            "--no-overwrite-unmanaged",
        ],
    )
    assert out.exit_code == 0, out.output
    # flags propagate
    assert captured.get("ActivatePlugins") is True
    assert captured.get("PublishWorkflows") is False
    assert captured.get("OverwriteUnmanagedCustomizations") is False
