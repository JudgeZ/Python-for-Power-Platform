from __future__ import annotations

import importlib
import json
import sys
from types import SimpleNamespace

import pytest
import typer


class StubDataverseClient:
    def __init__(self, token_getter, host: str | None = None):
        self.token = token_getter() if callable(token_getter) else None
        self.host = host


class StubPowerPagesClient:
    last_instance: "StubPowerPagesClient | None" = None

    def __init__(self, dv):
        self.dv = dv
        self.download_kwargs: dict[str, object] | None = None
        self.upload_args: tuple[str, str] | None = None
        self.upload_kwargs: dict[str, object] | None = None
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
        provider = SimpleNamespace(files=["file1", "file2"], skipped=0)
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

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    manifest = {"natural_keys": {"adx_webpages": ["adx_name"]}}
    (site_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def fake_diff_permissions(dv, website_id, src, *, key_config):
        fake_diff_permissions.called_with = {
            "website_id": website_id,
            "src": src,
            "key_config": key_config,
        }
        return [
            SimpleNamespace(entityset="adx_webroles", action="add", key=("role", "site")),
            SimpleNamespace(entityset="adx_webrolepermissions", action="remove", key=("perm",)),
        ]

    fake_diff_permissions.called_with = {}
    monkeypatch.setattr("pacx.cli.pages.diff_permissions", fake_diff_permissions)

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
    assert fake_diff_permissions.called_with["website_id"] == "site123"
    assert fake_diff_permissions.called_with["key_config"] == {
        "adx_webpages": ["adx_name"],
        "adx_webfiles": ["filename"],
    }
