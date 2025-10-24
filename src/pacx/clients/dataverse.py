
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
        """Configure a Dataverse client for the given environment.

        Args:
            token_getter: Callable that supplies bearer tokens for requests.
            host: Dataverse hostname (e.g. ``org.crm.dynamics.com``).
            api_path: Base path for the Web API endpoint.
            use_https: When ``True`` build an ``https`` URL, otherwise ``http``.
        """
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
        """List solutions from the Dataverse environment.

        Args:
            select: Optional comma-separated columns for ``$select``.
            filter: Optional ``$filter`` expression limiting results.
            top: Maximum number of solutions to retrieve.

        Returns:
            Parsed :class:`Solution` models for each entry in the response.
        """
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
        """Export a solution as a ZIP payload.

        Args:
            req: Request model containing solution name and export options.

        Returns:
            Raw bytes of the exported solution package.
        """
        payload = req.model_dump()
        resp = self.http.post("ExportSolution", json=payload)
        data = resp.json()
        b64 = data.get("ExportSolutionFile", "")
        return base64.b64decode(b64)

    def import_solution(self, req: ImportSolutionRequest) -> None:
        """Import a solution package into the environment.

        Args:
            req: Request model containing the base64 solution payload and
                import configuration.
        """
        payload = req.model_dump()
        self.http.post("ImportSolution", json=payload)

    def publish_all(self) -> None:
        """Trigger a publish-all operation for customizations."""

        self.http.post("PublishAllXml")

    # ---- Generic CRUD ----
    def whoami(self) -> Dict[str, Any]:
        """Return the identity details of the calling user."""

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
        """List entities for an entity set using standard OData options.

        Args:
            entityset: Dataverse entity set logical name.
            select: Optional ``$select`` columns.
            filter: Optional ``$filter`` expression.
            top: Maximum number of rows to request.
            orderby: Optional ``$orderby`` expression.

        Returns:
            JSON response payload from the Dataverse Web API.
        """
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
        """Retrieve a single record by ID."""

        path = f"{entityset}({record_id})"
        resp = self.http.get(path)
        return resp.json()

    def create_record(self, entityset: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Dataverse record and return metadata about the result.

        Args:
            entityset: Dataverse entity set logical name.
            data: JSON payload describing the new record.

        Returns:
            Dict containing the ``entityUrl`` header and any JSON response.
        """
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
        """Replace or merge fields on an existing record.

        Args:
            entityset: Dataverse entity set logical name.
            record_id: Primary key GUID formatted string.
            data: Fields to patch into the record.
        """
        path = f"{entityset}({record_id})"
        self.http.patch(path, headers={"If-Match": "*"}, json=data)

    def delete_record(self, entityset: str, record_id: str) -> None:
        """Delete a record from Dataverse."""

        path = f"{entityset}({record_id})"
        self.http.delete(path)

    # ---- Import Job helpers ----
    def get_import_job(self, job_id: str) -> Dict[str, Any]:
        """Fetch status for a solution import job."""

        resp = self.http.get(f"importjobs({job_id})")
        return resp.json()

    def wait_for_import_job(self, job_id: str, *, interval: float = 2.0, timeout: float = 600.0) -> Dict[str, Any]:
        """Poll an import job until completion or timeout.

        Args:
            job_id: Import job identifier (GUID string).
            interval: Seconds to wait between polling attempts.
            timeout: Maximum seconds to wait before raising ``TimeoutError``.

        Returns:
            Final job status payload retrieved from Dataverse.
        """
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
