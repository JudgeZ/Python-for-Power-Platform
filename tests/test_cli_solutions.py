from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer


class StubDataverseClient:
    last_instance: StubDataverseClient | None = None

    def __init__(self, token_getter, host: str | None = None):
        self.token = token_getter() if callable(token_getter) else None
        self.host = host
        self.list_called = False
        self.export_requests: list[object] = []
        self.import_requests: list[object] = []
        self.wait_calls: list[tuple[str, float, float]] = []
        self.publish_count = 0
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

    def export_solution(self, request):
        self.export_requests.append(request)
        return b"zip-bytes"

    def import_solution(self, request):
        self.import_requests.append(request)

    def wait_for_import_job(self, job_id: str, *, interval: float, timeout: float):
        self.wait_calls.append((job_id, interval, timeout))
        return {"status": "Completed"}

    def publish_all(self):
        self.publish_count += 1


@pytest.fixture(autouse=True)
def reset_stub():
    StubDataverseClient.last_instance = None


@pytest.fixture(autouse=True)
def fake_access_token(monkeypatch):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "test-token")


@pytest.fixture
def cli_app(monkeypatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    for candidate in (str(repo_root), str(src_dir)):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app


def test_list_solutions(monkeypatch, cli_runner, cli_app):
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)

    result = cli_runner.invoke(cli_app, ["solution", "list"])

    assert result.exit_code == 0
    assert "core_solution  Core Solution  v1.2.3.4" in result.stdout
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.host == "example.crm.dynamics.com"
    assert stub.list_called is True


def test_export_solution_writes_zip(monkeypatch, cli_runner, cli_app, tmp_path):
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)
    output_path = tmp_path / "exported.zip"

    result = cli_runner.invoke(
        cli_app,
        [
            "solution",
            "export",
            "--host",
            "example.crm.dynamics.com",
            "--name",
            "contoso",
            "--managed",
            "--out",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.read_bytes() == b"zip-bytes"
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.export_requests, "expected export_solution to be called"
    request = stub.export_requests[0]
    assert getattr(request, "SolutionName", None) == "contoso"
    assert getattr(request, "Managed", None) is True


def test_import_solution_waits_and_reports(monkeypatch, cli_runner, cli_app, tmp_path):
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)
    solution_zip = tmp_path / "solution.zip"
    solution_zip.write_bytes(b"zip-bytes")

    result = cli_runner.invoke(
        cli_app,
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


def test_publish_all(monkeypatch, cli_runner, cli_app):
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)

    result = cli_runner.invoke(
        cli_app,
        ["solution", "publish-all", "--host", "example.crm.dynamics.com"],
    )

    assert result.exit_code == 0
    assert "Published all customizations" in result.stdout
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.publish_count == 1


def test_pack_and_unpack(monkeypatch, cli_runner, cli_app, tmp_path):
    calls: list[tuple[str, Path, Path]] = []

    def record_pack(src: str, dest: str) -> None:
        calls.append(("pack", Path(src), Path(dest)))

    def record_unpack(src: str, dest: str) -> None:
        calls.append(("unpack", Path(src), Path(dest)))

    monkeypatch.setattr("pacx.cli.solution.pack_solution_folder", record_pack)
    monkeypatch.setattr("pacx.cli.solution.unpack_solution_zip", record_unpack)

    src_dir = tmp_path / "solution"
    src_dir.mkdir()
    out_zip = tmp_path / "solution.zip"

    pack_result = cli_runner.invoke(
        cli_app,
        ["solution", "pack", "--src", str(src_dir), "--out", str(out_zip)],
    )
    unpack_result = cli_runner.invoke(
        cli_app,
        ["solution", "unpack", "--file", str(out_zip), "--out", str(src_dir / "out")],
    )

    assert pack_result.exit_code == 0
    assert unpack_result.exit_code == 0
    assert ("pack", src_dir, out_zip) in calls
    assert ("unpack", out_zip, src_dir / "out") in calls


def test_pack_sp_and_unpack_sp(monkeypatch, cli_runner, cli_app, tmp_path):
    calls: list[tuple[str, Path, Path]] = []

    def record_pack(src: str, dest: str) -> None:
        calls.append(("pack-sp", Path(src), Path(dest)))

    def record_unpack(src: str, dest: str) -> None:
        calls.append(("unpack-sp", Path(src), Path(dest)))

    monkeypatch.setattr("pacx.cli.solution.pack_from_source", record_pack)
    monkeypatch.setattr("pacx.cli.solution.unpack_to_source", record_unpack)

    src_dir = tmp_path / "solution_sp"
    src_dir.mkdir()
    out_zip = tmp_path / "solution_sp.zip"

    pack_result = cli_runner.invoke(
        cli_app,
        ["solution", "pack-sp", "--src", str(src_dir), "--out", str(out_zip)],
    )
    unpack_result = cli_runner.invoke(
        cli_app,
        ["solution", "unpack-sp", "--file", str(out_zip), "--out", str(src_dir / "src")],
    )

    assert pack_result.exit_code == 0
    assert unpack_result.exit_code == 0
    assert ("pack-sp", src_dir, out_zip) in calls
    assert ("unpack-sp", out_zip, src_dir / "src") in calls


def test_legacy_action_export(monkeypatch, cli_runner, cli_app, tmp_path):
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)
    output_path = tmp_path / "legacy.zip"

    result = cli_runner.invoke(
        cli_app,
        [
            "solution",
            "--action",
            "export",
            "--name",
            "legacy",
            "--out",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    # Typer secho defaults to stdout so the warning appears in the captured output.
    assert "Deprecated: action-style" in result.stdout
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.export_requests, "expected legacy export to delegate to export command"


def test_legacy_action_unknown(cli_runner, cli_app):
    result = cli_runner.invoke(cli_app, ["solution", "--action", "unknown"])

    assert result.exit_code != 0
    assert "Unknown solution action" in result.output

def test_pack_sp_and_unpack_sp(monkeypatch, cli_runner, cli_app, tmp_path):
    calls: list[tuple[str, Path, Path]] = []

    def record_pack(src: str, dest: str) -> None:
        calls.append(("pack-sp", Path(src), Path(dest)))

    def record_unpack(src: str, dest: str) -> None:
        calls.append(("unpack-sp", Path(src), Path(dest)))

    monkeypatch.setattr("pacx.cli.solution.pack_from_source", record_pack)
    monkeypatch.setattr("pacx.cli.solution.unpack_to_source", record_unpack)

    src_dir = tmp_path / "sp"
    src_dir.mkdir()
    out_zip = tmp_path / "solution.zip"

    pack_result = cli_runner.invoke(
        cli_app,
        ["solution", "pack-sp", "--src", str(src_dir), "--out", str(out_zip)],
    )
    unpack_result = cli_runner.invoke(
        cli_app,
        [
            "solution",
            "unpack-sp",
            "--file",
            str(out_zip),
            "--out",
            str(src_dir / "out"),
        ],
    )

    assert pack_result.exit_code == 0
    assert unpack_result.exit_code == 0
    assert ("pack-sp", src_dir, out_zip) in calls
    assert ("unpack-sp", out_zip, src_dir / "out") in calls


def test_legacy_action_option_warns_and_dispatches(monkeypatch, cli_runner, cli_app):
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)

    result = cli_runner.invoke(cli_app, ["solution", "--action", "list"])

    assert result.exit_code == 0
    assert "core_solution  Core Solution  v1.2.3.4" in result.stdout
    assert "Deprecated: action-style solution invocations" in result.stdout


def test_legacy_action_option_accepts_extra_args(monkeypatch, cli_runner, cli_app, tmp_path):
    monkeypatch.setattr("pacx.cli.solution.DataverseClient", StubDataverseClient)
    output_path = tmp_path / "legacy-export.zip"

    result = cli_runner.invoke(
        cli_app,
        [
            "solution",
            "--action",
            "export",
            "--name",
            "legacy",
            "--host",
            "legacy.crm.dynamics.com",
            "--out",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.read_bytes() == b"zip-bytes"
    stub = StubDataverseClient.last_instance
    assert stub is not None
    assert stub.host == "legacy.crm.dynamics.com"
    assert stub.export_requests, "expected export_solution to be called"
    request = stub.export_requests[0]
    assert getattr(request, "SolutionName", None) == "legacy"


def test_legacy_action_unknown_command(monkeypatch, cli_runner, cli_app):
    result = cli_runner.invoke(cli_app, ["solution", "--action", "unknown"], catch_exceptions=False)

    assert result.exit_code != 0
    combined_output = result.stdout + (result.stderr or "")
    assert "Unknown solution action" in combined_output
