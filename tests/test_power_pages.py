
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
        params={"$select": "adx_webpageid,adx_name,adx_partialurl", "$filter": f"_adx_websiteid_value eq {website_id}", "$top": 5000},
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webpageid": "w1", "adx_name": "Home", "adx_partialurl": "/"}]}))
    # Mock webfiles
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
        params={"$select": "adx_webfileid,adx_name,adx_partialurl", "$filter": f"_adx_websiteid_value eq {website_id}", "$top": 5000},
    ).mock(return_value=httpx.Response(200, json={"value": [{"adx_webfileid": "f1", "adx_name": "logo.png", "adx_partialurl": "logo.png"}]}))

    pp = PowerPagesClient(dv)
    out = pp.download_site(website_id, tmp_path, include_files=True)
    assert (Path(out) / "pages").exists()
    assert (Path(out) / "files").exists()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _prepare_site(tmp_path: Path) -> Path:
    site_dir = Path(tmp_path) / "site"
    (site_dir / "pages").mkdir(parents=True)
    (site_dir / "files").mkdir(parents=True)
    return site_dir


def test_pages_upload_replace_strategy_default(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site_dir = _prepare_site(tmp_path)
    _write_json(site_dir / "pages" / "home.json", {"adx_webpageid": "w1", "adx_name": "Home"})
    _write_json(site_dir / "files" / "logo.json", {"adx_webfileid": "f1", "adx_name": "logo.png"})

    # Mocks for update
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(return_value=httpx.Response(204))
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles(f1)").mock(return_value=httpx.Response(204))

    pp.upload_site("id", str(site_dir))


def test_pages_upload_skip_existing(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site_dir = _prepare_site(tmp_path)
    _write_json(site_dir / "pages" / "home.json", {"adx_webpageid": "w1", "adx_name": "Home"})

    route = respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(return_value=httpx.Response(204))

    pp.upload_site("id", str(site_dir), strategy="skip-existing")

    assert not route.called


def test_pages_upload_merge_strategy(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site_dir = _prepare_site(tmp_path)
    _write_json(site_dir / "pages" / "home.json", {"adx_webpageid": "w1", "adx_name": "Home", "adx_partialurl": "/"})

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(
        return_value=httpx.Response(200, json={"adx_webpageid": "w1", "adx_name": "Old", "adx_custom": "x"})
    )
    route = respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(return_value=httpx.Response(204))

    pp.upload_site("id", str(site_dir), strategy="merge")

    assert route.called
    body = json.loads(route.calls[0].request.content)
    assert body["adx_name"] == "Home"
    assert body["adx_custom"] == "x"


def test_pages_upload_create_only(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site_dir = _prepare_site(tmp_path)
    _write_json(site_dir / "pages" / "home.json", {"adx_webpageid": "w1", "adx_name": "Home"})
    _write_json(site_dir / "pages" / "new.json", {"adx_name": "New"})

    patch_route = respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(return_value=httpx.Response(204))
    post_route = respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages").mock(return_value=httpx.Response(204))

    pp.upload_site("id", str(site_dir), strategy="create-only")

    assert not patch_route.called
    assert post_route.called
