
from __future__ import annotations

import base64
from pathlib import Path

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import PowerPagesClient, download_webfile_binaries


def test_download_webfile_binaries(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    # Fake site with one webfile
    wf = {"adx_webfileid": "wf1", "adx_name": "logo.png", "adx_partialurl": "logo.png"}
    # Mock annotation fetch
    data = base64.b64encode(b"hello").decode("ascii")
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/annotations",
        params={"$select": "annotationid,filename,documentbody,_objectid_value", "$filter": "_objectid_value eq wf1", "$top": 50},
    ).mock(return_value=httpx.Response(200, json={"value": [{"annotationid":"n1","filename":"logo.png","documentbody": data}]}))

    out_dir = tmp_path / "site"
    out_dir.mkdir()
    download_webfile_binaries(pp, [wf], str(out_dir))

    assert (Path(out_dir) / "files_bin" / "logo.png").read_bytes() == b"hello"


def test_download_site_triggers_binary_export(tmp_path, respx_mock, token_getter, monkeypatch):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)
    website_id = "00000000-0000-0000-0000-000000000000"

    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages",
        params={
            "$select": "adx_webpageid,adx_name,adx_partialurl,_adx_websiteid_value",
            "$filter": f"_adx_websiteid_value eq {website_id}",
            "$top": 5000,
        },
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webpageid": "p1", "adx_name": "Home", "adx_partialurl": "/"}]}))
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
        params={
            "$select": "adx_webfileid,adx_name,adx_partialurl,_adx_websiteid_value",
            "$filter": f"_adx_websiteid_value eq {website_id}",
            "$top": 5000,
        },
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webfileid": "f1", "adx_name": "logo.png", "adx_partialurl": "logo.png"}]}))

    captured: dict[str, object] = {}

    def fake_download(self, webfiles, out_dir):
        captured["webfiles"] = webfiles
        captured["out_dir"] = out_dir

    monkeypatch.setattr("pacx.clients.power_pages.download_webfile_binaries", fake_download)

    out_dir = pp.download_site(
        website_id,
        tmp_path,
        tables="adx_webpages,adx_webfiles",
        binaries=True,
    )

    assert captured["out_dir"] == out_dir
    webfiles = captured["webfiles"]
    assert isinstance(webfiles, list)
    assert webfiles and webfiles[0]["adx_webfileid"] == "f1"
