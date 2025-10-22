
from __future__ import annotations

import base64
from pathlib import Path

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import PowerPagesClient


def test_download_webfile_binaries(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    # Fake site with one webfile
    wf = {"adx_webfileid": "wf1", "adx_name": "logo.png", "adx_partialurl": "logo.png"}
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
        params={
            "$select": "adx_webfileid,adx_name,adx_partialurl",
            "$filter": "_adx_websiteid_value eq site",
            "$top": 1,
        },
    ).mock(return_value=httpx.Response(200, json={"value": [wf]}))
    # Mock annotation fetch
    data = base64.b64encode(b"hello").decode("ascii")
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/annotations",
        params={"$select": "annotationid,filename,documentbody,_objectid_value", "$filter": "_objectid_value eq wf1", "$top": 50},
    ).mock(return_value=httpx.Response(200, json={"value": [{"annotationid":"n1","filename":"logo.png","documentbody": data}]}))

    out_dir = pp.download_site("site", tmp_path, tables="adx_webfiles", top=1, binaries=True)

    assert (Path(out_dir) / "files_bin" / "logo.png").read_bytes() == b"hello"
    checksum = (Path(out_dir) / "files_bin" / "logo.png.sha256").read_text(encoding="utf-8")
    assert len(checksum) == 64
