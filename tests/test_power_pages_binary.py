
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
    # Mock annotation fetch
    data = base64.b64encode(b"hello").decode("ascii")
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/annotations",
        params={"$select": "annotationid,filename,documentbody,_objectid_value", "$filter": "_objectid_value eq wf1", "$top": 50},
    ).mock(return_value=httpx.Response(200, json={"value": [{"annotationid":"n1","filename":"logo.png","documentbody": data}]}))

    out_dir = pp.download_site("site", tmp_path, tables="core", top=1, binaries=False)  # create folder layout
    pp.download_webfile_binaries([wf], out_dir)

    assert (Path(out_dir) / "files_bin" / "logo.png").read_bytes() == b"hello"
