from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from ..http_client import HttpClient
from ..models.dataverse import (
    ApplySolutionUpgradeRequest,
    CloneAsPatchRequest,
    CloneAsPatchResponse,
    CloneAsSolutionRequest,
    CloneAsSolutionResponse,
    DeleteAndPromoteRequest,
    ExportSolutionAsManagedRequest,
    ExportSolutionRequest,
    ExportSolutionUpgradeRequest,
    ExportTranslationRequest,
    ImportSolutionRequest,
    ImportTranslationRequest,
    Solution,
    StageSolutionRequest,
    StageSolutionResponse,
)
from ..utils.guid import sanitize_guid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataverseOperationHandle:
    """Metadata returned by Dataverse long-running operations."""

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def has_operation(self) -> bool:
        """Return ``True`` when an operation URL is provided."""

        return bool(self.operation_location)


class DataverseClient:
    """Client for Dataverse Web API (v9.2)."""

    def __init__(
        self,
        token_getter: Callable[[], str],
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
        normalized_api_path = "/" + api_path.lstrip("/")
        raw_host = host.strip()
        if not raw_host:
            raise ValueError("Dataverse host must not be empty")

        parsed = urlparse(raw_host)
        if parsed.scheme:
            scheme = parsed.scheme
            netloc = parsed.netloc or parsed.path
            path = parsed.path if parsed.netloc else ""
        else:
            scheme = "https" if use_https else "http"
            parsed = urlparse(f"{scheme}://{raw_host}")
            netloc = parsed.netloc or parsed.path
            path = parsed.path

        if not netloc:
            raise ValueError(f"Invalid Dataverse host: {host!r}")

        clean_path = path.rstrip("/")
        if clean_path and not clean_path.startswith("/"):
            clean_path = f"/{clean_path}"

        base_path = f"{clean_path}{normalized_api_path}" if clean_path else normalized_api_path
        base_url = f"{scheme}://{netloc}{base_path}"
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

    def close(self) -> None:
        """Close the underlying HTTP session."""

        self.http.close()

    def __enter__(self) -> DataverseClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ---- Solution operations ----
    def list_solutions(
        self, select: str | None = None, filter: str | None = None, top: int | None = None
    ) -> list[Solution]:
        """List solutions from the Dataverse environment.

        Args:
            select: Optional comma-separated columns for ``$select``.
            filter: Optional ``$filter`` expression limiting results.
            top: Maximum number of solutions to retrieve.

        Returns:
            Parsed :class:`Solution` models for each entry in the response.
        """
        params: dict[str, Any] = {}
        if select:
            params["$select"] = select
        if filter:
            params["$filter"] = filter
        if top is not None:
            params["$top"] = top
        resp = self.http.get("solutions", params=params)
        data = cast(dict[str, Any], resp.json())
        return [Solution.model_validate(o) for o in data.get("value", [])]

    @staticmethod
    def _parse_response_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.content:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive logging
            logger.debug("Failed to decode Dataverse response payload", exc_info=True)
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    def _post_action(
        self, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[httpx.Response, dict[str, Any]]:
        resp = self.http.post(path, json=payload)
        data = self._parse_response_dict(resp)
        return resp, data

    @staticmethod
    def _operation_handle(resp: httpx.Response, data: dict[str, Any]) -> DataverseOperationHandle:
        return DataverseOperationHandle(resp.headers.get("Operation-Location"), data)

    def export_solution(self, req: ExportSolutionRequest) -> bytes:
        """Export a solution as a ZIP payload.

        Args:
            req: Request model containing solution name and export options.

        Returns:
            Raw bytes of the exported solution package.
        """
        payload = req.model_dump(exclude_none=True)
        _, data = self._post_action("ExportSolution", payload)
        b64 = data.get("ExportSolutionFile", "")
        return base64.b64decode(b64)

    def export_solution_as_managed(self, req: ExportSolutionAsManagedRequest) -> bytes:
        """Export a managed solution package."""

        payload = req.model_dump(exclude_none=True)
        _, data = self._post_action("ExportSolutionAsManaged", payload)
        b64 = data.get("ExportSolutionFile", "")
        return base64.b64decode(b64)

    def export_solution_upgrade(self, req: ExportSolutionUpgradeRequest) -> bytes:
        """Export a solution upgrade package."""

        payload = req.model_dump(exclude_none=True)
        _, data = self._post_action("ExportSolutionUpgrade", payload)
        b64 = data.get("ExportSolutionFile", "")
        return base64.b64decode(b64)

    def export_translation(self, req: ExportTranslationRequest) -> bytes:
        """Export localized solution translations."""

        payload = req.model_dump(exclude_none=True)
        _, data = self._post_action("ExportTranslation", payload)
        b64 = data.get("ExportTranslationFile", "")
        return base64.b64decode(b64)

    def import_solution(self, req: ImportSolutionRequest) -> DataverseOperationHandle:
        """Import a solution package into the environment.

        Args:
            req: Request model containing the base64 solution payload and
                import configuration.
        """
        payload = req.model_dump(exclude_none=True)
        resp, data = self._post_action("ImportSolution", payload)
        return self._operation_handle(resp, data)

    def stage_solution(self, req: StageSolutionRequest) -> DataverseOperationHandle:
        """Stage a solution for upgrade validation."""

        payload = req.model_dump(exclude_none=True)
        resp, data = self._post_action("StageSolution", payload)
        if data:
            try:
                parsed = StageSolutionResponse.model_validate(data)
                data = parsed.model_dump(exclude_none=True)
            except Exception:  # pragma: no cover - keep raw payload
                logger.debug("Unexpected StageSolution response payload", exc_info=True)
        return self._operation_handle(resp, data)

    def apply_solution_upgrade(self, req: ApplySolutionUpgradeRequest) -> DataverseOperationHandle:
        """Apply a previously staged solution upgrade."""

        payload = req.model_dump(exclude_none=True)
        resp, data = self._post_action("ApplySolutionUpgrade", payload)
        return self._operation_handle(resp, data)

    def import_translation(self, req: ImportTranslationRequest) -> DataverseOperationHandle:
        """Import localized solution translations."""

        payload = req.model_dump(exclude_none=True)
        resp, data = self._post_action("ImportTranslation", payload)
        return self._operation_handle(resp, data)

    def clone_as_patch(self, req: CloneAsPatchRequest) -> CloneAsPatchResponse:
        """Clone an existing solution as a patch."""

        payload = req.model_dump(exclude_none=True)
        _, data = self._post_action("CloneAsPatch", payload)
        return CloneAsPatchResponse.model_validate(data)

    def clone_as_solution(self, req: CloneAsSolutionRequest) -> CloneAsSolutionResponse:
        """Promote a patch solution back into the primary managed solution."""

        payload = req.model_dump(exclude_none=True)
        _, data = self._post_action("CloneAsSolution", payload)
        return CloneAsSolutionResponse.model_validate(data)

    def delete_and_promote(self, req: DeleteAndPromoteRequest) -> DataverseOperationHandle:
        """Delete a patch solution and promote the base solution."""

        payload = req.model_dump(exclude_none=True)
        resp, data = self._post_action("DeleteAndPromote", payload)
        return self._operation_handle(resp, data)

    def publish_all(self) -> None:
        """Trigger a publish-all operation for customizations."""

        self.http.post("PublishAllXml")

    # ---- Solution intelligence helpers ----
    def _get_solution_id_by_name(self, solution_name: str) -> str:
        """Return solutionid for the given ``solution_name`` or raise ``ValueError``."""

        items = self.list_solutions(
            select="solutionid,uniquename", filter=f"uniquename eq '{solution_name}'"
        )
        for s in items:
            if s.uniquename and s.solutionid and s.uniquename.lower() == solution_name.lower():
                return s.solutionid
        raise ValueError(f"Solution not found: {solution_name}")

    def get_solution_dependencies(self, solution_name: str) -> list[dict[str, Any]]:
        """Fetch dependency records for a solution by unique name.

        Returns a list of dicts parsed from the OData ``value`` array. This is a
        minimal helper intended for CLI reporting; the structure is left opaque
        to callers to keep the client surface small.
        """

        sid = self._get_solution_id_by_name(solution_name)
        resp = self.http.get(f"solutions({sid})/dependencies")
        data = cast(dict[str, Any], resp.json())
        value = data.get("value", [])
        return [v for v in value if isinstance(v, dict)]

    def get_solution_components(
        self, solution_name: str, component_type: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch solution components, optionally filtered by component type id."""

        sid = self._get_solution_id_by_name(solution_name)
        params: dict[str, Any] = {}
        if component_type is not None:
            params["$filter"] = f"componenttype eq {component_type}"
        resp = self.http.get(f"solutions({sid})/solutioncomponents", params=params)
        data = cast(dict[str, Any], resp.json())
        value = data.get("value", [])
        return [v for v in value if isinstance(v, dict)]

    def list_connection_references(self, solution_name: str) -> list[dict[str, Any]]:
        """Return connection references for a solution by unique name.

        Resolves the solution id and queries the ``connectionreferences``
        navigation under the solution. Returns the raw dicts from the OData
        ``value`` array to keep the client surface small and flexible.
        """

        sid = self._get_solution_id_by_name(solution_name)
        resp = self.http.get(f"solutions({sid})/connectionreferences")
        data = cast(dict[str, Any], resp.json())
        value = data.get("value", [])
        return [v for v in value if isinstance(v, dict)]

    # ---- Generic CRUD ----
    def whoami(self) -> dict[str, Any]:
        """Return the identity details of the calling user."""

        resp = self.http.get("WhoAmI()")
        return cast(dict[str, Any], resp.json())

    def list_records(
        self,
        entityset: str,
        *,
        select: str | None = None,
        filter: str | None = None,
        top: int | None = None,
        orderby: str | None = None,
    ) -> dict[str, Any]:
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
        params: dict[str, Any] = {}
        if select:
            params["$select"] = select
        if filter:
            params["$filter"] = filter
        if top is not None:
            params["$top"] = top
        if orderby:
            params["$orderby"] = orderby
        resp = self.http.get(entityset, params=params)
        return cast(dict[str, Any], resp.json())

    def get_record(self, entityset: str, record_id: str) -> dict[str, Any]:
        """Retrieve a single record by ID."""

        clean_id = sanitize_guid(record_id)
        path = f"{entityset}({clean_id})"
        resp = self.http.get(path)
        return cast(dict[str, Any], resp.json())

    def create_record(self, entityset: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a Dataverse record and return metadata about the result.

        Args:
            entityset: Dataverse entity set logical name.
            data: JSON payload describing the new record.

        Returns:
            Dict containing the ``entityUrl`` header and any JSON response.
        """
        resp = self.http.post(entityset, json=data)
        out: dict[str, Any] = {}
        loc = resp.headers.get("OData-EntityId") or resp.headers.get("Location")
        if loc:
            out["entityUrl"] = loc
        try:
            j = resp.json()
            if isinstance(j, dict):
                out.update(j)
        except Exception:  # pragma: no cover - best-effort parse
            logger.debug("Failed to decode Dataverse create_record response", exc_info=True)
        return out

    def update_record(self, entityset: str, record_id: str, data: dict[str, Any]) -> None:
        """Replace or merge fields on an existing record.

        Args:
            entityset: Dataverse entity set logical name.
            record_id: Primary key GUID formatted string.
            data: Fields to patch into the record.
        """
        clean_id = sanitize_guid(record_id)
        path = f"{entityset}({clean_id})"
        self.http.patch(path, headers={"If-Match": "*"}, json=data)

    def delete_record(self, entityset: str, record_id: str) -> None:
        """Delete a record from Dataverse."""

        clean_id = sanitize_guid(record_id)
        path = f"{entityset}({clean_id})"
        self.http.delete(path)

    # ---- Import Job helpers ----
    def get_import_job(self, job_id: str) -> dict[str, Any]:
        """Fetch status for a solution import job."""

        clean_id = sanitize_guid(job_id)
        resp = self.http.get(f"importjobs({clean_id})")
        return cast(dict[str, Any], resp.json())

    def wait_for_import_job(
        self, job_id: str, *, interval: float = 2.0, timeout: float = 600.0
    ) -> dict[str, Any]:
        """Poll an import job until completion or timeout.

        Args:
            job_id: Import job identifier (GUID string).
            interval: Seconds to wait between polling attempts.
            timeout: Maximum seconds to wait before raising ``TimeoutError``.

        Returns:
            Final job status payload retrieved from Dataverse.
        """
        from ..utils.poller import poll_until

        def get_status() -> dict[str, Any]:
            try:
                return self.get_import_job(job_id)
            except Exception:
                return {"status": "Unknown"}

        def is_done(s: dict[str, Any]) -> bool:
            # Heuristic: look for progress >= 100 or state indicating completion
            for k in ("progress", "percent", "percentagecomplete"):
                v = s.get(k)
                if isinstance(v, int | float) and v >= 100:
                    return True
            state = str(s.get("statecode") or s.get("status") or "").lower()
            return state in {"completed", "succeeded", "failed"}

        def get_progress(s: dict[str, Any]) -> int | None:
            for k in ("progress", "percent", "percentagecomplete"):
                v = s.get(k)
                if isinstance(v, int | float):
                    return int(v)
            return None

        return poll_until(get_status, is_done, get_progress, interval=interval, timeout=timeout)
