from __future__ import annotations

import base64
import json

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import PowerPagesClient


def _mock_site(respx_mock: respx.Router) -> None:
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "adx_webfileid": "wf1",
                        "adx_name": "logo.png",
                        "adx_partialurl": "logo.png",
                        "_adx_websiteid_value": "site",
                        "adx_virtualfilestorepath": "https://storage/f/logo.png",
                    }
                ]
            },
        )
    )

    for _folder, entityset in (
        ("websites", "adx_websites"),
        ("pages", "adx_webpages"),
        ("snippets", "adx_contentsnippets"),
        ("templates", "adx_pagetemplates"),
        ("sitemarkers", "adx_sitemarkers"),
    ):
        respx_mock.get(
            f"https://example.crm.dynamics.com/api/data/v9.2/{entityset}",
        ).mock(return_value=httpx.Response(200, json={"value": []}))


def test_download_with_annotation_provider(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    _mock_site(respx_mock)

    data = base64.b64encode(b"hello").decode("ascii")
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/annotations",
        params={
            "$select": "annotationid,filename,documentbody,_objectid_value",
            "$filter": "_objectid_value eq wf1",
            "$top": 50,
        },
    ).mock(
        return_value=httpx.Response(
            200,
            json={"value": [{"annotationid": "n1", "filename": "logo.png", "documentbody": data}]},
        )
    )

    res = pp.download_site(
        "site",
        tmp_path,
        tables="core",
        binaries=True,
        provider_options={"annotations": {"top": 50}},
    )

    bin_file = res.output_path / "files_bin" / "logo.png"
    assert bin_file.read_bytes() == b"hello"
    manifest = json.loads((res.output_path / "manifest.json").read_text())
    assert manifest["providers"]["annotations"]["files"][0]["checksum"]


def test_annotation_provider_sanitizes_filename(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    _mock_site(respx_mock)

    payload_one = base64.b64encode(b"one").decode("ascii")
    payload_two = base64.b64encode(b"two").decode("ascii")
    payload_three = base64.b64encode(b"three").decode("ascii")
    payload_four = base64.b64encode(b"four").decode("ascii")
    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/annotations",
        params={
            "$select": "annotationid,filename,documentbody,_objectid_value",
            "$filter": "_objectid_value eq wf1",
            "$top": 50,
        },
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "annotationid": "n1",
                        "filename": "../secrets/logo.png",
                        "documentbody": payload_one,
                    },
                    {
                        "annotationid": "n2",
                        "filename": "..\\hidden\\config.json",
                        "documentbody": payload_two,
                    },
                    {
                        "annotationid": "n3",
                        "filename": "..\\",
                        "documentbody": payload_three,
                    },
                    {
                        "annotationid": "n4",
                        "filename": "./",
                        "documentbody": payload_four,
                    },
                ]
            },
        )
    )

    res = pp.download_site(
        "site",
        tmp_path,
        tables="core",
        binaries=True,
        provider_options={"annotations": {"top": 50}},
    )

    bin_dir = res.output_path / "files_bin"
    expected_files = {
        "logo.png",
        "logo.png.sha256",
        "config.json",
        "config.json.sha256",
        "n3.bin",
        "n3.bin.sha256",
        "n4.bin",
        "n4.bin.sha256",
    }
    assert {p.name for p in bin_dir.iterdir()} == expected_files
    # Ensure nothing escaped outside of the export directory.
    assert not (res.output_path / "logo.png").exists()
    assert not (res.output_path / "config.json").exists()


def test_download_with_azure_provider(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    _mock_site(respx_mock)

    blob = respx_mock.get("https://storage/f/logo.png").mock(
        return_value=httpx.Response(200, content=b"blob")
    )

    res = pp.download_site(
        "site",
        tmp_path,
        tables="core",
        binaries=False,
        binary_providers=["azure"],
    )

    assert blob.called
    assert (res.output_path / "files_virtual" / "logo.png").read_bytes() == b"blob"


def test_download_with_azure_provider_and_sas_query(
    monkeypatch, tmp_path, respx_mock, token_getter
):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "adx_webfileid": "wf1",
                        "adx_name": "logo.png",
                        "adx_partialurl": "logo.png",
                        "_adx_websiteid_value": "site",
                        "adx_virtualfilestorepath": "https://storage/f/logo.png?foo=1",
                    }
                ]
            },
        )
    )
    for entity in (
        "adx_websites",
        "adx_webpages",
        "adx_contentsnippets",
        "adx_pagetemplates",
        "adx_sitemarkers",
    ):
        respx_mock.get(
            f"https://example.crm.dynamics.com/api/data/v9.2/{entity}",
        ).mock(return_value=httpx.Response(200, json={"value": []}))

    monkeypatch.setenv("BLOB_SAS", "sv=1&sig=xyz")

    blob = respx_mock.get("https://storage/f/logo.png?foo=1&sv=1&sig=xyz").mock(
        return_value=httpx.Response(200, content=b"blob")
    )

    res = pp.download_site(
        "site",
        tmp_path,
        tables="core",
        binaries=False,
        binary_providers=["azure"],
        provider_options={"azure": {"sas_env": "BLOB_SAS"}},
    )

    assert blob.called
    assert (res.output_path / "files_virtual" / "logo.png").read_bytes() == b"blob"
