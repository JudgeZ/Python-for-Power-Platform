from __future__ import annotations

import base64

import httpx

from pacx.clients.dataverse import DataverseClient
from pacx.models.dataverse import ExportSolutionRequest, ImportSolutionRequest


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
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/ImportSolution").mock(
        return_value=httpx.Response(204)
    )
    dv.import_solution(ImportSolutionRequest(CustomizationFile=b64))
    respx_mock.post("https://example.crm.dynamics.com/api/data/v9.2/PublishAllXml").mock(
        return_value=httpx.Response(204)
    )
    dv.publish_all()
