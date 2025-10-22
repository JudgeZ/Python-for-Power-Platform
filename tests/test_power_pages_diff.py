from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from pacx.cli import app
from pacx.clients.dataverse import DataverseClient
from pacx.power_pages.diff import diff_permissions

runner = CliRunner()


def test_diff_permissions_engine(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    site = Path(tmp_path)
    local_dir = site / "entitypermissions"
    local_dir.mkdir()
    local_perm = {"adx_name": "AllowAccounts", "_adx_websiteid_value": "site"}
    (local_dir / "perm.json").write_text(json.dumps(local_perm), encoding="utf-8")

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_entitypermissions").mock(
        return_value=httpx.Response(200, json={"value": [{"adx_name": "AllowAccounts", "_adx_websiteid_value": "site", "adx_accessrightsmask": 1}]})
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpageaccesscontrolrules").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webroles").mock(
        return_value=httpx.Response(200, json={"value": []})
    )

    diffs = diff_permissions(dv, "site", str(site))
    assert diffs
    assert diffs[0].action == "update"


def test_diff_permissions_cli(tmp_path, respx_mock, token_getter, monkeypatch):
    site = Path(tmp_path)
    (site / "entitypermissions").mkdir()
    (site / "manifest.json").write_text(json.dumps({"natural_keys": {}}), encoding="utf-8")
    (site / "entitypermissions" / "local.json").write_text(json.dumps({"adx_name": "Allow", "_adx_websiteid_value": "site"}), encoding="utf-8")

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_entitypermissions").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpageaccesscontrolrules").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webroles").mock(
        return_value=httpx.Response(200, json={"value": []})
    )

    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    monkeypatch.setenv("PACX_ACCESS_TOKEN", token_getter())

    result = runner.invoke(
        app,
        [
            "pages",
            "diff-permissions",
            "--website-id",
            "site",
            "--src",
            str(site),
        ],
    )
    assert result.exit_code == 0
    assert "create" in result.stdout
