from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer


class StubDataverseClient:
    def __init__(self, token_getter, host: str | None = None):
        self.token = token_getter() if callable(token_getter) else None
        self.host = host


class StubPowerPagesClient:
    last_instance: StubPowerPagesClient | None = None
    provider_errors: list[str] | None = None

    def __init__(self, dv):
        self.dv = dv
        self.download_kwargs: dict[str, object] | None = None
        self.upload_args: tuple[str, str] | None = None
        self.upload_kwargs: dict[str, object] | None = None
        self.diff_args: dict[str, object] | None = None
        StubPowerPagesClient.last_instance = self

    def download_site(
        self,
        website_id: str,
        out: str,
        *,
        tables: str,
        include_files: bool,
        binaries: bool,
        binary_providers: list[str] | None,
        provider_options: dict[str, dict[str, object]],
    ):
        self.download_kwargs = {
            "website_id": website_id,
            "out": out,
            "tables": tables,
            "include_files": include_files,
            "binaries": binaries,
            "binary_providers": binary_providers,
            "provider_options": provider_options,
        }
        provider = SimpleNamespace(
            files=["file1", "file2"],
            skipped=0,
            errors=list(self.provider_errors or []),
        )
        return SimpleNamespace(output_path=out, providers={"annotations": provider})

    def upload_site(
        self,
        website_id: str,
        src: str,
        *,
        tables: str,
        strategy: str,
        key_config: dict[str, list[str]],
    ):
        self.upload_args = (website_id, src)
        self.upload_kwargs = {
            "tables": tables,
            "strategy": strategy,
            "key_config": key_config,
        }

    def key_config_from_manifest(
        self,
        src_dir: str,
        overrides: dict[str, list[str]] | None = None,
    ) -> dict[str, list[str]]:
        path = Path(src_dir) / "manifest.json"
        merged: dict[str, list[str]] = {}
        if path.exists():
            data = json.loads(path.read_text())
            merged.update({k.lower(): list(v) for k, v in data.get("natural_keys", {}).items()})
        if overrides:
            for key, value in overrides.items():
                merged[key.lower()] = list(value)
        return merged

    def diff_permissions(
        self,
        website_id: str,
        base_dir: str,
        *,
        key_config: dict[str, list[str]] | None = None,
    ):
        self.diff_args = {
            "website_id": website_id,
            "base_dir": base_dir,
            "key_config": key_config,
        }
        return [
            SimpleNamespace(entityset="adx_webroles", action="add", key=("role", "site")),
            SimpleNamespace(entityset="adx_webrolepermissions", action="remove", key=("perm",)),
        ]


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
    StubPowerPagesClient.last_instance = None
    StubPowerPagesClient.provider_errors = None


def test_pages_download_reports_providers(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.DataverseClient", StubDataverseClient)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesClient", StubPowerPagesClient)

    out_dir = tmp_path / "site_out"

    result = cli_runner.invoke(
        app,
        [
            "pages",
            "download",
            "--website-id",
            "site123",
            "--tables",
            "core",
            "--binaries",
            "--binary-provider",
            "annotations",
            "--out",
            str(out_dir),
            "--provider-options",
            json.dumps({"annotations": {"foo": "bar"}}),
        ],
        env={
            "PACX_ACCESS_TOKEN": "test-token",
            "DATAVERSE_HOST": "example.crm.dynamics.com",
        },
    )

    assert result.exit_code == 0
    assert "Downloaded site to" in result.stdout
    assert "Provider annotations: 2 files, skipped=0" in result.stdout
    stub = StubPowerPagesClient.last_instance
    assert stub is not None
    assert stub.download_kwargs is not None
    assert stub.download_kwargs["binary_providers"] == ["annotations"]
    assert stub.download_kwargs["provider_options"] == {"annotations": {"foo": "bar"}}


def test_pages_download_reports_provider_errors(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.DataverseClient", StubDataverseClient)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesClient", StubPowerPagesClient)

    StubPowerPagesClient.provider_errors = [
        "Failed to download binary file asset.js",
        "Timeout while contacting provider API",
    ]

    out_dir = tmp_path / "site_out"

    result = cli_runner.invoke(
        app,
        [
            "pages",
            "download",
            "--website-id",
            "site123",
            "--tables",
            "core",
            "--out",
            str(out_dir),
        ],
        env={
            "PACX_ACCESS_TOKEN": "test-token",
            "DATAVERSE_HOST": "example.crm.dynamics.com",
        },
    )

    assert result.exit_code == 0
    assert "Provider annotations error: Failed to download binary file asset.js" in result.stdout
    assert "Provider annotations error: Timeout while contacting provider API" in result.stdout


def test_load_json_or_path_reads_file(tmp_path):
    from pacx.cli._pages_utils import load_json_or_path

    payload = {"a": 1}
    path = tmp_path / "opts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_json_or_path(str(path)) == payload


def test_merge_manifest_keys_uses_client(tmp_path):
    from pacx.cli._pages_utils import merge_manifest_keys

    class DummyClient:
        def key_config_from_manifest(self, src_dir, overrides=None):
            merged = {"adx_webpages": ["adx_partialurl"]}
            if overrides:
                merged.update(overrides)
            return merged

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    client = DummyClient()
    result = merge_manifest_keys(client, str(site_dir), {"adx_webfiles": ["filename"]})
    assert result["adx_webpages"] == ["adx_partialurl"]
    assert result["adx_webfiles"] == ["filename"]


def test_pages_upload_merges_key_configuration(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.DataverseClient", StubDataverseClient)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesClient", StubPowerPagesClient)

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    manifest = {"natural_keys": {"adx_webpages": ["adx_name"]}}
    (site_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    key_override = json.dumps({"adx_webfiles": ["filename"]})

    result = cli_runner.invoke(
        app,
        [
            "pages",
            "upload",
            "--website-id",
            "site123",
            "--tables",
            "core",
            "--src",
            str(site_dir),
            "--strategy",
            "merge",
            "--key-config",
            key_override,
        ],
        env={
            "PACX_ACCESS_TOKEN": "test-token",
            "DATAVERSE_HOST": "example.crm.dynamics.com",
        },
    )

    assert result.exit_code == 0
    assert "Uploaded site content" in result.stdout
    stub = StubPowerPagesClient.last_instance
    assert stub is not None
    assert stub.upload_kwargs is not None
    assert stub.upload_kwargs["strategy"] == "merge"
    assert stub.upload_kwargs["key_config"] == {
        "adx_webpages": ["adx_name"],
        "adx_webfiles": ["filename"],
    }


def test_pages_diff_permissions_lists_plan(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.DataverseClient", StubDataverseClient)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesClient", StubPowerPagesClient)

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    manifest = {"natural_keys": {"adx_webpages": ["adx_name"]}}
    (site_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = cli_runner.invoke(
        app,
        [
            "pages",
            "diff-permissions",
            "--website-id",
            "site123",
            "--src",
            str(site_dir),
            "--key-config",
            json.dumps({"adx_webfiles": ["filename"]}),
        ],
        env={
            "PACX_ACCESS_TOKEN": "test-token",
            "DATAVERSE_HOST": "example.crm.dynamics.com",
        },
    )

    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "Permission diff plan:"
    assert lines[1].startswith("- adx_webroles: add")
    assert lines[2].startswith("- adx_webrolepermissions: remove")
    stub = StubPowerPagesClient.last_instance
    assert stub is not None
    assert stub.diff_args is not None
    assert stub.diff_args["website_id"] == "site123"
    assert stub.diff_args["key_config"] == {
        "adx_webpages": ["adx_name"],
        "adx_webfiles": ["filename"],
    }


def test_pages_upload_rejects_string_key_config(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.DataverseClient", StubDataverseClient)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesClient", StubPowerPagesClient)

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    result = cli_runner.invoke(
        app,
        [
            "pages",
            "upload",
            "--website-id",
            "site123",
            "--src",
            str(site_dir),
            "--key-config",
            json.dumps({"adx_webpages": "adx_name"}),
        ],
        env={"DATAVERSE_HOST": "example.crm.dynamics.com"},
    )

    assert result.exit_code == 2
    assert "must map to an array of column names" in result.stderr


def test_pages_diff_permissions_rejects_string_key_config(monkeypatch, cli_runner, tmp_path):
    app = load_cli_app(monkeypatch)
    monkeypatch.setattr("pacx.cli.pages.DataverseClient", StubDataverseClient)
    monkeypatch.setattr("pacx.cli.pages.PowerPagesClient", StubPowerPagesClient)

    site_dir = tmp_path / "site"
    site_dir.mkdir()

    result = cli_runner.invoke(
        app,
        [
            "pages",
            "diff-permissions",
            "--website-id",
            "site123",
            "--src",
            str(site_dir),
            "--key-config",
            json.dumps({"adx_webpages": "adx_name"}),
        ],
        env={"DATAVERSE_HOST": "example.crm.dynamics.com"},
    )

    assert result.exit_code == 2
    assert "must map to an array of column names" in result.stderr
