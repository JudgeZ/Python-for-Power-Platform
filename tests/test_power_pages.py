from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import (
    CORE_TABLES,
    EXTRA_TABLES,
    PowerPagesClient,
)


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
            json={
                "value": [
                    {
                        "adx_webpageid": "w1",
                        "adx_name": "Home",
                        "adx_partialurl": "home",
                        "_adx_websiteid_value": website_id,
                    }
                ]
            },
        )
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "adx_webfileid": "f1",
                        "adx_name": "logo.png",
                        "adx_partialurl": "logo.png",
                        "_adx_websiteid_value": website_id,
                    }
                ]
            },
        )
    )
    _mock_empty_tables(respx_mock)

    pp = PowerPagesClient(dv)
    res = pp.download_site(website_id, tmp_path, include_files=True)
    assert (res.output_path / "pages").exists()
    assert (res.output_path / "files").exists()
    manifest = json.loads(res.manifest_path.read_text())
    assert manifest["website_id"] == website_id


def test_pages_download_handles_pagination(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    website_id = "00000000-0000-0000-0000-000000000000"

    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "adx_webpageid": "w1",
                            "adx_name": "Home",
                            "adx_partialurl": "home",
                            "_adx_websiteid_value": website_id,
                        }
                    ],
                    "@odata.nextLink": "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages?$skiptoken=abc",
                },
            ),
            httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "adx_webpageid": "w2",
                            "adx_name": "About",
                            "adx_partialurl": "about",
                            "_adx_websiteid_value": website_id,
                        }
                    ]
                },
            ),
        ]
    )
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    _mock_empty_tables(respx_mock)

    pp = PowerPagesClient(dv)
    res = pp.download_site(website_id, tmp_path, include_files=True)
    pages = sorted((res.output_path / "pages").glob("*.json"))
    assert len(pages) == 2
    names = {json.loads(path.read_text(encoding="utf-8"))["adx_name"] for path in pages}
    assert names == {"Home", "About"}


def test_pages_upload_with_ids(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    files_dir = site / "files"
    pages_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)
    (pages_dir / "home.json").write_text(
        json.dumps({"adx_webpageid": "w1", "adx_name": "Home"}), encoding="utf-8"
    )
    (files_dir / "logo.json").write_text(
        json.dumps({"adx_webfileid": "f1", "adx_name": "logo.png"}), encoding="utf-8"
    )

    def assert_if_match(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("If-Match") == "*"
        return httpx.Response(204)

    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(w1)").mock(
        side_effect=assert_if_match
    )
    respx_mock.patch("https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles(f1)").mock(
        side_effect=assert_if_match
    )

    pp.upload_site("id", str(site))


def test_pages_upload_natural_keys(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    page_data = {
        "adx_name": "Home",
        "adx_partialurl": "home/intro",
        "_adx_websiteid_value": "site'id",
    }
    (pages_dir / "home.json").write_text(json.dumps(page_data), encoding="utf-8")

    expected_segment = (
        "adx_webpages(adx_partialurl='home%2Fintro',_adx_websiteid_value='site%27%27id')"
    )

    def responder(request: httpx.Request) -> httpx.Response:
        raw_path = request.url.raw_path.decode("utf-8")
        assert expected_segment in raw_path
        assert request.headers.get("If-Match") == "*"
        return httpx.Response(204)

    respx_mock.patch(
        "https://example.crm.dynamics.com/api/data/v9.2/" + expected_segment
    ).mock(side_effect=responder)

    pp.upload_site("site", str(site), strategy="replace")


def test_pages_upload_natural_keys_merge(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "home.json").write_text(
        json.dumps({"adx_partialurl": "home", "_adx_websiteid_value": "site", "adx_name": "New"}),
        encoding="utf-8",
    )

    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')"
    ).mock(
        return_value=httpx.Response(
            200, json={"adx_name": "Old", "adx_partialurl": "home", "_adx_websiteid_value": "site"}
        )
    )

    def patcher(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["adx_name"] == "New"
        assert body["adx_partialurl"] == "home"
        assert request.headers.get("If-Match") == "*"
        return httpx.Response(204)

    respx_mock.patch(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')"
    ).mock(side_effect=patcher)

    pp.upload_site("site", str(site), strategy="merge")


def test_pages_upload_natural_keys_merge_creates_when_missing(
    tmp_path, respx_mock, token_getter
):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "home.json").write_text(
        json.dumps({"adx_partialurl": "home", "_adx_websiteid_value": "site", "adx_name": "New"}),
        encoding="utf-8",
    )

    get_route = respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/"
        "adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')"
    ).mock(return_value=httpx.Response(404, json={"error": "Not Found"}))

    post_route = respx_mock.post(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages"
    ).mock(return_value=httpx.Response(201, headers={"OData-EntityId": "entity"}))

    patch_url = (
        "https://example.crm.dynamics.com/api/data/v9.2/"
        "adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')"
    )
    patch_route = respx_mock.patch(patch_url).mock(return_value=httpx.Response(204))

    pp.upload_site("site", str(site), strategy="merge")

    assert get_route.called
    assert post_route.called
    assert not patch_route.called


def test_pages_upload_natural_keys_skip_existing(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    pages_dir = site / "pages"
    pages_dir.mkdir(parents=True)
    page_data = {"adx_partialurl": "home", "_adx_websiteid_value": "site", "adx_name": "Existing"}
    (pages_dir / "home.json").write_text(json.dumps(page_data), encoding="utf-8")

    get_route = respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')"
    ).mock(return_value=httpx.Response(200, json=page_data))
    patch_route = respx_mock.patch(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webpages(adx_partialurl='home',_adx_websiteid_value='site')"
    ).mock(return_value=httpx.Response(204))

    pp.upload_site("site", str(site), strategy="skip-existing")

    assert get_route.called
    assert not patch_route.called


def test_select_sets_iterable_subset():
    selected = PowerPagesClient._select_sets(["pages"])
    pages_tuple = next(item for item in CORE_TABLES if item[0] == "pages")
    assert selected == [pages_tuple]


def test_select_sets_core_alias_with_extra():
    selected = PowerPagesClient._select_sets("core,weblinks")
    weblinks_tuple = next(item for item in EXTRA_TABLES if item[0] == "weblinks")
    assert selected == list(CORE_TABLES) + [weblinks_tuple]


def test_normalize_provider_inputs_requires_files(token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    with pytest.raises(ValueError):
        pp.normalize_provider_inputs(
            binaries=True,
            binary_providers=None,
            include_files=False,
        )


def test_normalize_provider_inputs_roundtrip(token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    providers, options = pp.normalize_provider_inputs(
        binaries=False,
        binary_providers=["annotations"],
        include_files=True,
        provider_options={"annotations": {"foo": "bar"}},
    )

    assert providers == ["annotations"]
    assert options == {"annotations": {"foo": "bar"}}


def test_key_config_from_manifest_merges_overrides(tmp_path, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    site = Path(tmp_path) / "site"
    site.mkdir()
    manifest = {"natural_keys": {"adx_webpages": ["adx_name"]}}
    (site / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    merged = pp.key_config_from_manifest(str(site), overrides={"adx_webfiles": ["filename"]})

    assert merged["adx_webpages"] == ["adx_name"]
    assert merged["adx_webfiles"] == ["filename"]
