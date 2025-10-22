
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from ..http_client import HttpClient
from ..models.dataverse import Solution, ExportSolutionRequest, ImportSolutionRequest


class DataverseClient:
    """Client for Dataverse Web API (v9.2)."""

    def __init__(
        self,
        token_getter,
        host: str,
        api_path: str = "/api/data/v9.2",
        use_https: bool = True,
    ) -> None:
        scheme = "https" if use_https else "http"
        base_url = f"{scheme}://{host}{api_path}"
        self.http = HttpClient(
            base_url,
            token_getter=token_getter,
            default_headers={
                "OData-Version": "4.0",
                "OData-MaxVersion": "4.0",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

    # ---- Solution operations ----
    def list_solutions(self, select: Optional[str] = None, filter: Optional[str] = None, top: Optional[int] = None) -> List[Solution]:
        params: Dict[str, Any] = {}
        if select:
            params["$select"] = select
        if filter:
            params["$filter"] = filter
        if top is not None:
            params["$top"] = top
        resp = self.http.get("solutions", params=params)
        data = resp.json()
        return [Solution.model_validate(o) for o in data.get("value", [])]

    def export_solution(self, req: ExportSolutionRequest) -> bytes:
        payload = req.model_dump()
        resp = self.http.post("ExportSolution", json=payload)
        data = resp.json()
        b64 = data.get("ExportSolutionFile", "")
        return base64.b64decode(b64)

    def import_solution(self, req: ImportSolutionRequest) -> None:
        payload = req.model_dump()
        self.http.post("ImportSolution", json=payload)

    def publish_all(self) -> None:
        self.http.post("PublishAllXml")

    # ---- Generic CRUD ----
    def whoami(self) -> Dict[str, Any]:
        resp = self.http.get("WhoAmI()")
        return resp.json()

    def list_records(
        self,
        entityset: str,
        *,
        select: Optional[str] = None,
        filter: Optional[str] = None,
        top: Optional[int] = None,
        orderby: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if select:
            params["$select"] = select
        if filter:
            params["$filter"] = filter
        if top is not None:
            params["$top"] = top
        if orderby:
            params["$orderby"] = orderby
        resp = self.http.get(entityset, params=params)
        return resp.json()

    def get_record(self, entityset: str, record_id: str) -> Dict[str, Any]:
        path = f"{entityset}({record_id})"
        resp = self.http.get(path)
        return resp.json()

    def create_record(self, entityset: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.http.post(entityset, json=data)
        out: Dict[str, Any] = {}
        loc = resp.headers.get("OData-EntityId") or resp.headers.get("Location")
        if loc:
            out["entityUrl"] = loc
        try:
            j = resp.json()
            if isinstance(j, dict):
                out.update(j)
        except Exception:
            pass
        return out

    def update_record(self, entityset: str, record_id: str, data: Dict[str, Any]) -> None:
        path = f"{entityset}({record_id})"
        self.http.patch(path, headers={"If-Match": "*"}, json=data)

    def delete_record(self, entityset: str, record_id: str) -> None:
        path = f"{entityset}({record_id})"
        self.http.delete(path)


# ---- Import Job helpers ----
def get_import_job(self, job_id: str) -> Dict[str, Any]:
    resp = self.http.get(f"importjobs({job_id})")
    return resp.json()

def wait_for_import_job(self, job_id: str, *, interval: float = 2.0, timeout: float = 600.0) -> Dict[str, Any]:
    from ..utils.poller import poll_until

    def get_status() -> Dict[str, Any]:
        try:
            return self.get_import_job(job_id)
        except Exception:
            return {"status": "Unknown"}

    def is_done(s: Dict[str, Any]) -> bool:
        # Heuristic: look for progress >= 100 or state indicating completion
        for k in ("progress", "percent", "percentagecomplete"):
            v = s.get(k)
            if isinstance(v, (int, float)) and v >= 100:
                return True
        state = str(s.get("statecode") or s.get("status") or "").lower()
        return state in {"completed", "succeeded", "failed"}

    def get_progress(s: Dict[str, Any]):
        for k in ("progress", "percent", "percentagecomplete"):
            v = s.get(k)
            if isinstance(v, (int, float)):
                return int(v)
        return None

    return poll_until(get_status, is_done, get_progress, interval=interval, timeout=timeout)
