from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import respx

from pacx.clients.dataverse import DataverseClient
from pacx.clients.power_pages import PowerPagesClient


def _mock_site(
    respx_mock: respx.Router, *, webfile_override: dict[str, object] | None = None
) -> None:
    webfile = {
        "adx_webfileid": "wf1",
        "adx_name": "logo.png",
        "adx_partialurl": "logo.png",
        "_adx_websiteid_value": "site",
        "adx_virtualfilestorepath": "https://storage/f/logo.png",
    }
    if webfile_override:
        webfile.update(webfile_override)

    respx_mock.get(
        "https://example.crm.dynamics.com/api/data/v9.2/adx_webfiles",
    ).mock(
        return_value=httpx.Response(
            200,
            json={"value": [webfile]},
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
            json={
                "value": [
                    {
                        "annotationid": "n1",
                        "filename": "../../escape.bin",
                        "documentbody": data,
                    },
                    {
                        "annotationid": "n2",
                        "filename": "..\\evil.bin",
                        "documentbody": data,
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

    escape_file = res.output_path / "files_bin" / "escape.bin"
    evil_file = res.output_path / "files_bin" / "evil.bin"
    assert escape_file.read_bytes() == b"hello"
    assert evil_file.read_bytes() == b"hello"
    assert not (res.output_path / "escape.bin").exists()
    assert (res.output_path / "files_bin" / "escape.bin.sha256").exists()
    assert (res.output_path / "files_bin" / "evil.bin.sha256").exists()
    manifest = json.loads((res.output_path / "manifest.json").read_text())
    annotation_files = {
        entry["path"]: entry for entry in manifest["providers"]["annotations"]["files"]
    }
    expected_paths = {
        Path("files_bin", name).as_posix(): name
        for name in ("escape.bin", "evil.bin")
    }
    assert set(annotation_files) == set(expected_paths)
    for path in expected_paths:
        assert annotation_files[path]["checksum"]
    assert {
        entry["extra"]["annotationid"] for entry in annotation_files.values()
    } == {"n1", "n2"}


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


def test_download_with_azure_provider_sanitizes_paths(tmp_path, respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    pp = PowerPagesClient(dv)

    _mock_site(respx_mock, webfile_override={"adx_name": "", "adx_partialurl": "..\\evil.bin"})

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
    evil_file = res.output_path / "files_virtual" / "evil.bin"
    assert evil_file.read_bytes() == b"blob"
    assert not (res.output_path / "evil.bin").exists()
    manifest = json.loads((res.output_path / "manifest.json").read_text())
    azure_files = manifest["providers"]["azure-blob"]["files"]
    assert {
        entry["path"] for entry in azure_files
    } == {Path("files_virtual", "evil.bin").as_posix()}


def test_download_with_azure_provider_preserves_unique_paths(
    tmp_path, respx_mock, token_getter
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
                        "adx_partialurl": "images/logo.png",
                        "_adx_websiteid_value": "site",
                        "adx_virtualfilestorepath": "https://storage/f/images/logo.png",
                    },
                    {
                        "adx_webfileid": "wf2",
                        "adx_name": "logo.png",
                        "adx_partialurl": "header/logo.png",
                        "_adx_websiteid_value": "site",
                        "adx_virtualfilestorepath": "https://storage/f/header/logo.png",
                    },
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

    first_blob = respx_mock.get("https://storage/f/images/logo.png").mock(
        return_value=httpx.Response(200, content=b"img"),
    )
    second_blob = respx_mock.get("https://storage/f/header/logo.png").mock(
        return_value=httpx.Response(200, content=b"hdr"),
    )

    res = pp.download_site(
        "site",
        tmp_path,
        tables="core",
        binaries=False,
        binary_providers=["azure"],
    )

    assert first_blob.called
    assert second_blob.called
    first_target = res.output_path / "files_virtual" / "images_logo.png"
    second_target = res.output_path / "files_virtual" / "header_logo.png"
    assert first_target.read_bytes() == b"img"
    assert second_target.read_bytes() == b"hdr"

    manifest = json.loads((res.output_path / "manifest.json").read_text())
    azure_files = manifest["providers"]["azure-blob"]["files"]
    assert {entry["path"] for entry in azure_files} == {
        Path("files_virtual", "images_logo.png").as_posix(),
        Path("files_virtual", "header_logo.png").as_posix(),
    }


def test_download_with_azure_provider_and_sas_query(monkeypatch, tmp_path, respx_mock, token_getter):
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
