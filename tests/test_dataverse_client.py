from __future__ import annotations

import base64
import json

import httpx
import pytest

from pacx.clients.dataverse import DataverseClient, DataverseOperationHandle
from pacx.models.dataverse import (
    ApplySolutionUpgradeRequest,
    CloneAsPatchRequest,
    CloneAsSolutionRequest,
    DeleteAndPromoteRequest,
    ExportSolutionAsManagedRequest,
    ExportSolutionRequest,
    ExportSolutionUpgradeRequest,
    ExportTranslationRequest,
    ImportSolutionRequest,
    ImportTranslationRequest,
    StageSolutionRequest,
)


def test_list_solutions(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/solutions").mock(
        return_value=httpx.Response(
            200, json={"value": [{"uniquename": "sol", "version": "1.0.0.0"}]}
        )
    )
    sols = dv.list_solutions()
    assert len(sols) == 1
    assert sols[0].uniquename == "sol"


def test_export_import_publish(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    b = b"zipdata"
    b64 = base64.b64encode(b).decode("ascii")
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ExportSolution").mock(
        return_value=httpx.Response(200, json={"ExportSolutionFile": b64})
    )
    data = dv.export_solution(ExportSolutionRequest(SolutionName="mysol", Managed=False))
    assert data == b
    def import_responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["CustomizationFile"] == b64
        return httpx.Response(
            202,
            headers={"Operation-Location": "https://example.crm.dynamics.com/ops/import"},
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ImportSolution").mock(
        side_effect=import_responder
    )
    handle = dv.import_solution(ImportSolutionRequest(CustomizationFile=b))
    assert isinstance(handle, DataverseOperationHandle)
    assert handle.operation_location == "https://example.crm.dynamics.com/ops/import"
    assert handle.metadata == {}
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/PublishAllXml").mock(
        return_value=httpx.Response(204)
    )
    dv.publish_all()


def test_stage_solution_handles_operation_header(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")
    expected_b64 = base64.b64encode(b"zipdata").decode("ascii")

    def responder(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["CustomizationFile"] == expected_b64
        return httpx.Response(
            202,
            headers={"Operation-Location": "https://example.crm.dynamics.com/ops/stage"},
            json={"StageSolutionResults": {"StageSolutionUploadId": "upload1"}},
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/StageSolution").mock(
        side_effect=responder
    )
    handle = dv.stage_solution(StageSolutionRequest(CustomizationFile=b"zipdata"))
    assert handle.operation_location == "https://example.crm.dynamics.com/ops/stage"
    assert handle.metadata == {"StageSolutionResults": {"StageSolutionUploadId": "upload1"}}


def test_apply_delete_and_translation_import(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ApplySolutionUpgrade").mock(
        return_value=httpx.Response(
            200,
            headers={"Operation-Location": "https://example.crm.dynamics.com/ops/upgrade"},
        )
    )
    upgrade = dv.apply_solution_upgrade(ApplySolutionUpgradeRequest(SolutionName="sol"))
    assert upgrade.operation_location == "https://example.crm.dynamics.com/ops/upgrade"

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/DeleteAndPromote").mock(
        return_value=httpx.Response(
            200,
            headers={"Operation-Location": "https://example.crm.dynamics.com/ops/promote"},
        )
    )
    promote = dv.delete_and_promote(DeleteAndPromoteRequest(UniqueName="sol_patch"))
    assert promote.operation_location == "https://example.crm.dynamics.com/ops/promote"

    expected_b64 = base64.b64encode(b"xliff").decode("ascii")

    def import_translation_responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["TranslationFile"] == expected_b64
        return httpx.Response(
            202,
            headers={"Operation-Location": "https://example.crm.dynamics.com/ops/translation"},
        )

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ImportTranslation").mock(
        side_effect=import_translation_responder
    )
    translation = dv.import_translation(
        ImportTranslationRequest(TranslationFile=b"xliff", ImportJobId="job1")
    )
    assert translation.operation_location == "https://example.crm.dynamics.com/ops/translation"


def test_clone_and_export_variants(respx_mock, token_getter):
    dv = DataverseClient(token_getter, host="example.crm.dynamics.com")

    def clone_patch_responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body == {
            "ParentSolutionUniqueName": "parent",
            "DisplayName": "Patch",
            "VersionNumber": "1.0.1.0",
        }
        return httpx.Response(200, json={"SolutionId": "patch-guid"})

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/CloneAsPatch").mock(
        side_effect=clone_patch_responder
    )
    patch_resp = dv.clone_as_patch(
        CloneAsPatchRequest(
            ParentSolutionUniqueName="parent", DisplayName="Patch", VersionNumber="1.0.1.0"
        )
    )
    assert patch_resp.SolutionId == "patch-guid"

    def clone_solution_responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body == {
            "ParentSolutionUniqueName": "patch",
            "DisplayName": "Primary",
            "VersionNumber": "1.1.0.0",
        }
        return httpx.Response(200, json={"SolutionId": "solution-guid"})

    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/CloneAsSolution").mock(
        side_effect=clone_solution_responder
    )
    solution_resp = dv.clone_as_solution(
        CloneAsSolutionRequest(
            ParentSolutionUniqueName="patch", DisplayName="Primary", VersionNumber="1.1.0.0"
        )
    )
    assert solution_resp.SolutionId == "solution-guid"

    expected_zip = base64.b64encode(b"managed").decode("ascii")

    def export_managed_responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body == {"SolutionName": "mysol", "Managed": True}
        return httpx.Response(200, json={"ExportSolutionFile": expected_zip})

    respx_mock.post(
        "https://example.crm.dynamics.com/api/data/v9.2/ExportSolutionAsManaged"
    ).mock(side_effect=export_managed_responder)
    managed = dv.export_solution_as_managed(ExportSolutionAsManagedRequest(SolutionName="mysol"))
    assert managed == b"managed"

    expected_upgrade_zip = base64.b64encode(b"upgrade").decode("ascii")
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ExportSolutionUpgrade").mock(
        return_value=httpx.Response(200, json={"ExportSolutionFile": expected_upgrade_zip})
    )
    upgrade = dv.export_solution_upgrade(ExportSolutionUpgradeRequest(SolutionName="mysol"))
    assert upgrade == b"upgrade"

    expected_translation_zip = base64.b64encode(b"translation").decode("ascii")
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ExportTranslation").mock(
        return_value=httpx.Response(200, json={"ExportTranslationFile": expected_translation_zip})
    )
    translation_zip = dv.export_translation(ExportTranslationRequest(SolutionName="mysol"))
    assert translation_zip == b"translation"


@pytest.mark.parametrize(
    "host,use_https,expected",
    [
        ("example.crm.dynamics.com", True, "https://example.crm.dynamics.com/api/data/v9.2"),
        ("example.crm.dynamics.com", False, "http://example.crm.dynamics.com/api/data/v9.2"),
        ("https://example.crm.dynamics.com", True, "https://example.crm.dynamics.com/api/data/v9.2"),
        ("https://example.crm.dynamics.com/", True, "https://example.crm.dynamics.com/api/data/v9.2"),
        ("https://example.crm.dynamics.com/custom", True, "https://example.crm.dynamics.com/custom/api/data/v9.2"),
        ("http://example.crm.dynamics.com", True, "http://example.crm.dynamics.com/api/data/v9.2"),
    ],
)
def test_host_normalization(token_getter, host, use_https, expected):
    dv = DataverseClient(token_getter, host=host, use_https=use_https)
    assert dv.http.base_url == expected


def test_host_normalization_rejects_empty(token_getter):
    with pytest.raises(ValueError):
        DataverseClient(token_getter, host="   ")
