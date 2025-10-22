from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import PowerPagesClient


def _mock_empty_tables(respx_mock: respx.Router) -> None:
    for entity in (
        "adx_websites",
        "adx_contentsnippets",
        "adx_pagetemplates",
        "adx_sitemarkers",
    ):
        respx_mock.get(f"https://example.crm.dynamics.com/api/data/v9.2/{entity}").mock(
            return_value=httpx.Response(200, json={"value": []})
        )


def test_pages_download(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    website_id = "00000000-0000-0000-0000-000000000000"

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages").mock(
        return_value=httpx.Response(
            200,
            json={"value": [{"adx_webpageid": "w1", "adx_name": "Home", "adx_partialurl": "home", "_adx_websiteid_value": website_id}]},
        )
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles").mock(
        return_value=httpx.Response(
            200,
            json={"value": [{"adx_webfileid": "f1", "adx_name": "logo.png", "adx_partialurl": "logo.png", "_adx_websiteid_value": website_id}]},
        )
    )
    _mock_empty_tables(respx_mock)

    pp = PowerPagesClient(dv)
    res = pp.download_site(website_id, tmp_path, include_files=True)
    assert (res.output_path / "pages").exists()
    assert (res.output_path / "files").exists()
    manifest = json.loads(res.manifest_path.read_text())
    assert manifest["website_id"] == website_id


def test_pages_upload_with_ids(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    files_dir = site / "files"
    pages_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)
    (pages_dir / "home.json").write_text(json.dumps({"adx_webpageid": "w1", "adx_name": "Home"}), encoding="utf-8")
    (files_dir / "logo.json").write_text(json.dumps({"adx_webfileid": "f1", "adx_name": "logo.png"}), encoding="utf-8")

    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(return_value=httpx.Response(204))
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles(f1)").mock(return_value=httpx.Response(204))

    pp.upload_site("id", str(site))


def test_pages_upload_natural_keys(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    page_data = {"adx_name": "Home", "adx_partialurl": "home", "_adx_websiteid_value": "site"}
    (pages_dir / "home.json").write_text(json.dumps(page_data), encoding="utf-8")

    def responder(request: httpx.Request) -> httpx.Response:
        assert "adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')" in request.url.path
        return httpx.Response(204)

    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')").mock(side_effect=responder)

    pp.upload_site("site", str(site), strategy="replace")


def test_pages_upload_natural_keys_merge(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "home.json").write_text(json.dumps({"adx_partialurl": "home", "_adx_websiteid_value": "site", "adx_name": "New"}), encoding="utf-8")

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')").mock(
        return_value=httpx.Response(200, json={"adx_name": "Old", "adx_partialurl": "home", "_adx_websiteid_value": "site"})
    )

    def patcher(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["adx_name"] == "New"
        assert body["adx_partialurl"] == "home"
        return httpx.Response(204)

    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')").mock(side_effect=patcher)

    pp.upload_site("site", str(site), strategy="merge")


def test_pages_upload_natural_keys_skip_existing(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    page_data = {"adx_partialurl": "home", "_adx_websiteid_value": "site", "adx_name": "Existing"}
    (pages_dir / "home.json").write_text(json.dumps(page_data), encoding="utf-8")

    get_route = respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')").mock(
        return_value=httpx.Response(200, json=page_data)
    )
    patch_route = respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')").mock(
        return_value=httpx.Response(204)
    )

    pp.upload_site("site", str(site), strategy="skip-existing")

    assert get_route.called
    assert not patch_route.called
