
from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import PowerPagesClient


def test_pages_download(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    website_id = "00000000-0000-0000-0000-000000000000"
    # Mock webpages
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages",
        params={
            "$select": "adx_webpageid,adx_name,adx_partialurl,_adx_websiteid_value",
            "$filter": f"_adx_websiteid_value eq {website_id}",
            "$top": 5000,
        },
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webpageid": "w1", "adx_name": "Home", "adx_partialurl": "/"}]}))
    # Mock webfiles
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
        params={
            "$select": "adx_webfileid,adx_name,adx_partialurl,_adx_websiteid_value",
            "$filter": f"_adx_websiteid_value eq {website_id}",
            "$top": 5000,
        },
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webfileid": "f1", "adx_name": "logo.png", "adx_partialurl": "logo.png"}]}))

    pp = PowerPagesClient(dv)
    out = pp.download_site(
        website_id,
        tmp_path,
        tables="adx_webpages,adx_webfiles",
        include_files=True,
    )
    assert (Path(out) / "pages").exists()
    assert (Path(out) / "files").exists()


def test_pages_download_skip_files(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    website_id = "00000000-0000-0000-0000-000000000000"
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages",
        params={
            "$select": "adx_webpageid,adx_name,adx_partialurl,_adx_websiteid_value",
            "$filter": f"_adx_websiteid_value eq {website_id}",
            "$top": 5000,
        },
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webpageid": "w1", "adx_name": "Home", "adx_partialurl": "/"}]}))
    files_route = respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
        params={
            "$select": "adx_webfileid,adx_name,adx_partialurl,_adx_websiteid_value",
            "$filter": f"_adx_websiteid_value eq {website_id}",
            "$top": 5000,
        },
    ).mock(return_value=httpx.Response(200, json={"value": []}))

    pp = PowerPagesClient(dv)
    out = pp.download_site(
        website_id,
        tmp_path,
        tables="adx_webpages,adx_webfiles",
        include_files=False,
    )

    pages_dir = Path(out) / "pages"
    assert pages_dir.exists()
    assert not (Path(out) / "files").exists()
    assert not files_route.called

    meta = json.loads((Path(out) / "site.json").read_text(encoding="utf-8"))
    assert meta["summary"] == {"pages": 1}


def test_pages_upload(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    pages_dir = Path(tmp_path) / "site" / "pages"
    files_dir = Path(tmp_path) / "site" / "files"
    pages_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)
    (pages_dir / "home.json").write_text(json.dumps({"adx_webpageid": "w1", "adx_name": "Home"}), encoding="utf-8")
    (files_dir / "logo.json").write_text(json.dumps({"adx_webfileid": "f1", "adx_name": "logo.png"}), encoding="utf-8")

    # Mocks for update
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(return_value=httpx.Response(204))
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles(f1)").mock(return_value=httpx.Response(204))

    pp.upload_site("id", str(Path(tmp_path) / "site"))
