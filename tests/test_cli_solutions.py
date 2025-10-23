from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest
import typer


class StubDataverseClient:
    last_instance: "StubDataverseClient | None" = None

    def __init__(self, token_getter, host: str | None = None):
        self.token = token_getter() if callable(token_getter) else None
        self.host = host
        self.list_called = False
        self.import_requests: list[object] = []
        self.wait_calls: list[tuple[str, float, float]] = []
        StubDataverseClient.last_instance = self

    def list_solutions(self, *, select: str | None = None):
        self.list_called = True
        return [
            SimpleNamespace(
                uniquename="core_solution",
                friendlyname="Core Solution",
                version="1.2.3.4",
            )
        ]

    def export_solution(self, request):  # pragma: no cover - not used in these tests
        raise AssertionError("Unexpected export invocation")

    def import_solution(self, request):
        self.import_requests.append(request)

    def wait_for_import_job(self, job_id: str, *, interval: float, timeout: float):
        self.wait_calls.append((job_id, interval, timeout))
        return {"status": "Completed"}

    def publish_all(self):  # pragma: no cover - not used
        raise AssertionError("Unexpected publish invocation")


def load_cli_app(monkeypatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


@pytest.fixture(autouse=True)
def reset_stub():
    StubDataverseClient.last_instance = None


def test_solution_list_formats_output(monkeypatch, cli_runner):
    app = load_cli_app(monkeypatch)
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    monkeypatch.setattr("pacx.cli.power_platform.DataverseClient", StubDataverseClient)

    result = cli_runner.invoke(
        app,
        ["solution", "list"],
        env={
            "PACX_ACCESS_TOKEN": "test-token",
            "DATAVERSE_HOST": "example.crm.dynamics.com",
        },
    )

    assert result.exit_code == 0
    assert "core_solution  Core Solution  v1.2.3.4" in result.stdout
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.list_called is True


def test_solution_import_waits_and_reports(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.power_platform.DataverseClient", StubDataverseClient)

    solution_zip = tmp_path / "solution.zip"
    solution_zip.write_bytes(b"zip-bytes")

    result = cli_runner.invoke(
        app,
        [
            "solution",
            "import",
            "--host",
            "example.crm.dynamics.com",
            "--file",
            str(solution_zip),
            "--import-job-id",
            "job123",
            "--wait",
        ],
        env={"PACX_ACCESS_TOKEN": "test-token"},
    )

    assert result.exit_code == 0
    assert "Import submitted" in result.stdout
    assert "job123" in result.stdout
    assert "Completed" in result.stdout
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.import_requests, "expected import_solution to be called"
    request = stub.import_requests[0]
    assert getattr(request, "ImportJobId", None) == "job123"
    assert stub.wait_calls == [("job123", 1.0, 600.0)]
