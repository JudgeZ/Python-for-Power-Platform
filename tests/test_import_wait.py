
from __future__ import annotations

import base64
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from pacx.cli import app
from pacx.clients.dataverse import DataverseClient

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

    @respx_mock.route(path__regex=r"https://example\\.crm\\.dynamics\\.com/api/data/v9\\.2/importjobs\\([0-9a-fA-F]+\\)")
    def import_job_route(request):
        call_count["n"] += 1
        if call_count["n"] < 2:
            return httpx.Response(200, json={"progress": 50})
        return httpx.Response(200, json={"progress": 100, "statecode": "Completed"})

    result = runner.invoke(app, ["solution", "import", "--file", str(z), "--wait"])
    assert result.exit_code == 0
    assert "Import submitted" in result.stdout


def test_dataverse_client_get_import_job(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    job_id = "abc123"
    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/importjobs({job_id})"
    ).mock(return_value=httpx.Response(200, json={"importjobid": job_id, "progress": 10}))

    payload = dv.get_import_job(job_id)

    assert payload["importjobid"] == job_id
    assert payload["progress"] == 10


def test_dataverse_client_wait_for_import_job_success(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    job_id = "deadbeef"
    call_count = {"n": 0}

    def callback(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(200, json={"progress": 25})
        return httpx.Response(200, json={"progress": 100, "statecode": "Completed"})

    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/importjobs({job_id})"
    ).mock(side_effect=callback)

    status = dv.wait_for_import_job(job_id, interval=0.0, timeout=1.0)

    assert status["statecode"].lower() == "completed"
    assert call_count["n"] >= 2


def test_dataverse_client_wait_for_import_job_handles_error_then_failure(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    job_id = "badcafe"
    responses = [
        httpx.Response(500, json={"error": {"message": "temporary"}}),
        httpx.Response(200, json={"progress": 100, "statecode": "Failed", "details": "boom"}),
    ]

    def callback(request):
        return responses.pop(0)

    respx_mock.get(
        f"https://example.crm.dynamics.com/api/data/v9.2/importjobs({job_id})"
    ).mock(side_effect=callback)

    status = dv.wait_for_import_job(job_id, interval=0.0, timeout=1.0)

    assert status["statecode"].lower() == "failed"
