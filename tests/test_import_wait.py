
from __future__ import annotations

import base64
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner
from pacx.cli import app

runner = CliRunner()


def test_solution_import_wait(monkeypatch, tmp_path, respx_mock):
    # Token and host
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")

    # Create a tiny "zip" file (content irrelevant)
    z = tmp_path / "s.zip"
    z.write_bytes(b"dummy")

    # Mock import submit
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ImportSolution").mock(return_value=httpx.Response(204))

    # Mock import job polling
    # Our CLI generates a uuid hex; we'll intercept by matching any id and returning progress then completed
    # We'll simulate two calls; use a route with a lambda to allow multiple responses
    job_url = "https://example.crm.dynamics.com/api/data/v9.2/importjobs"
    call_count = {"n": 0}

    respx_mock.get(
        url__regex=r"https://example\.crm\.dynamics\.com/api/data/v9\.2/importjobs\([0-9a-fA-F]+\)"
    ).mock(side_effect=[httpx.Response(200, json={"progress": 50}), httpx.Response(200, json={"progress": 100, "statecode": "Completed"})])

    result = runner.invoke(app, ["solution", "import", "--file", str(z), "--wait"])
    assert result.exit_code == 0
    assert "Import submitted" in result.stdout
