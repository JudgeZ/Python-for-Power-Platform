from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast
from urllib.parse import parse_qsl, urlparse

import httpx

from ..http_client import HttpClient
from ..models.power_platform import (
    AppPermissionAssignment,
    AppVersion,
    CloudFlow,
    EnvironmentSummary,
    FlowActionList,
    FlowRun,
    FlowRunDiagnostics,
    PowerApp,
)

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class OperationHandle:
    """Metadata returned by long-running Power Platform operations.

    Attributes:
        operation_location: Absolute or relative URL to poll for completion.
        metadata: Parsed JSON payload returned by the initial request.

    Examples:
        >>> handle = OperationHandle("https://api.powerplatform.com/.../operations/op1", {"status": "Accepted"})
        >>> handle.operation_id
        'op1'
    """

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def operation_id(self) -> str | None:
        """Return the trailing identifier from :attr:`operation_location`."""

        if not self.operation_location:
            return None
        return self.operation_location.rstrip("/").split("/")[-1]


@dataclass(frozen=True)
class AppVersionPage:
    """Container for a page of Power App version results."""

    versions: list[AppVersion]
    next_link: str | None = None
    continuation_token: str | None = None


@dataclass(frozen=True)
class FlowRunPage:
    """Container for paged results returned by flow run queries."""

    runs: list[FlowRun]
    continuation_token: str | None = None
    next_link: str | None = None


class PowerPlatformClient:
    """Client for Power Platform Admin & product APIs."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def _with_api_version(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            params.update(extra)
        return params

    @staticmethod
    def _parse_response_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    def _post_operation(
        self,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> OperationHandle:
        resp = self.http.post(path, params=params or self._with_api_version(), json=body)
        payload = self._parse_response_dict(resp)
        return OperationHandle(resp.headers.get("Operation-Location"), payload)

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> PowerPlatformClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def list_environments(self) -> list[EnvironmentSummary]:
        resp = self.http.get(
            "environmentmanagement/environments", params={"api-version": self.api_version}
        )
        data = cast(dict[str, Any], resp.json())
        return [EnvironmentSummary.model_validate(obj) for obj in data.get("value", [])]

    def get_environment(self, environment_id: str) -> EnvironmentSummary:
        resp = self.http.get(
            f"environmentmanagement/environments/{environment_id}",
            params={"api-version": self.api_version},
        )
        return EnvironmentSummary.model_validate(resp.json())

    def delete_environment(self, environment_id: str, validate_only: bool | None = None) -> None:
        params = {"api-version": self.api_version}
        if validate_only is not None:
            params["ValidateOnly"] = str(validate_only).lower()
        self.http.delete(f"environmentmanagement/environments/{environment_id}", params=params)

    def copy_environment(self, environment_id: str, payload: dict[str, Any]) -> OperationHandle:
        """Trigger a copy of the specified environment.

        Args:
            environment_id: Source environment identifier.
            payload: Copy options payload forwarded to the API.

        Returns:
            Operation metadata containing the polling URL and initial response body.
        """

        return self._post_operation(
            f"environmentmanagement/environments/{environment_id}:copy", body=payload
        )

    def reset_environment(self, environment_id: str, payload: dict[str, Any]) -> OperationHandle:
        """Reset an environment to a previous restore point."""

        return self._post_operation(
            f"environmentmanagement/environments/{environment_id}:reset", body=payload
        )

    def backup_environment(self, environment_id: str, payload: dict[str, Any]) -> OperationHandle:
        """Create a manual backup for the specified environment."""

        return self._post_operation(
            f"environmentmanagement/environments/{environment_id}:backup", body=payload
        )

    def restore_environment(self, environment_id: str, payload: dict[str, Any]) -> OperationHandle:
        """Restore an environment from a backup."""

        return self._post_operation(
            f"environmentmanagement/environments/{environment_id}:restore", body=payload
        )

    def list_environment_operations(self, environment_id: str) -> list[dict[str, Any]]:
        """List lifecycle operations for an environment."""

        resp = self.http.get(
            f"environmentmanagement/environments/{environment_id}/operations",
            params=self._with_api_version(),
        )
        data = self._parse_response_dict(resp)
        value = data.get("value")
        return cast(list[dict[str, Any]], value) if isinstance(value, list) else []

    def get_operation(self, operation_id: str) -> dict[str, Any]:
        """Fetch details for a lifecycle operation."""

        resp = self.http.get(
            f"environmentmanagement/operations/{operation_id}",
            params=self._with_api_version(),
        )
        return self._parse_response_dict(resp)

    def wait_for_operation(
        self, operation_url: str, *, interval: float = 2.0, timeout: float = 600.0
    ) -> dict[str, Any]:
        """Poll an operation URL until completion or timeout."""

        from ..utils.poller import poll_until

        done_states = {"succeeded", "failed", "canceled", "cancelled"}

        def get_status() -> dict[str, Any]:
            resp = self.http.get(operation_url)
            return self._parse_response_dict(resp)

        def is_done(status: dict[str, Any]) -> bool:
            state = str(status.get("status") or status.get("state") or "").lower()
            if state in done_states:
                return True
            return bool(status.get("endTime") or status.get("completedOn"))

        def get_progress(status: dict[str, Any]) -> int | None:
            for key in ("percentComplete", "progress", "percentage", "completionPercent"):
                value = status.get(key)
                if isinstance(value, (int, float)):
                    return int(value)
            return None

        return poll_until(get_status, is_done, get_progress, interval=interval, timeout=timeout)

    def list_environment_settings(self, environment_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"environmentmanagement/environments/{environment_id}/settings",
            params={"api-version": self.api_version},
        )
        return cast(dict[str, Any], resp.json())

    def upsert_environment_setting(self, environment_id: str, body: dict[str, Any]) -> None:
        self.http.post(
            f"environmentmanagement/environments/{environment_id}/settings",
            params={"api-version": self.api_version},
            json=body,
        )

    def list_environment_groups(self) -> list[dict[str, Any]]:
        """Return all environment groups."""

        resp = self.http.get(
            "environmentmanagement/environmentGroups", params=self._with_api_version()
        )
        data = self._parse_response_dict(resp)
        value = data.get("value")
        return cast(list[dict[str, Any]], value) if isinstance(value, list) else []

    def get_environment_group(self, group_id: str) -> dict[str, Any]:
        """Retrieve a single environment group."""

        resp = self.http.get(
            f"environmentmanagement/environmentGroups/{group_id}",
            params=self._with_api_version(),
        )
        return self._parse_response_dict(resp)

    def create_environment_group(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new environment group."""

        resp = self.http.post(
            "environmentmanagement/environmentGroups",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_response_dict(resp)

    def update_environment_group(self, group_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an existing environment group."""

        resp = self.http.patch(
            f"environmentmanagement/environmentGroups/{group_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_response_dict(resp)

    def delete_environment_group(self, group_id: str) -> OperationHandle:
        """Delete an environment group."""

        resp = self.http.delete(
            f"environmentmanagement/environmentGroups/{group_id}",
            params=self._with_api_version(),
        )
        payload = self._parse_response_dict(resp)
        return OperationHandle(resp.headers.get("Operation-Location"), payload)

    def apply_environment_group(
        self, group_id: str, environment_id: str
    ) -> OperationHandle:
        """Apply an environment group to an environment."""

        return self._post_operation(
            f"environmentmanagement/environmentGroups/{group_id}/environments/{environment_id}/apply"
        )

    def revoke_environment_group(
        self, group_id: str, environment_id: str
    ) -> OperationHandle:
        """Revoke an environment group from an environment."""

        return self._post_operation(
            f"environmentmanagement/environmentGroups/{group_id}/environments/{environment_id}/revoke"
        )

    def get_environment_group_operation(
        self, group_id: str, operation_id: str
    ) -> dict[str, Any]:
        """Fetch the status for an environment group operation."""

        resp = self.http.get(
            f"environmentmanagement/environmentGroups/{group_id}/operations/{operation_id}",
            params=self._with_api_version(),
        )
        return self._parse_response_dict(resp)

    def enable_managed_environment(self, environment_id: str) -> OperationHandle:
        """Enable managed environment governance controls."""

        return self._post_operation(
            f"environmentmanagement/environments/{environment_id}/managedGovernance/enable"
        )

    def disable_managed_environment(self, environment_id: str) -> OperationHandle:
        """Disable managed environment governance controls."""

        return self._post_operation(
            f"environmentmanagement/environments/{environment_id}/managedGovernance/disable"
        )

    def list_apps(
        self, environment_id: str, top: int | None = None, skiptoken: str | None = None
    ) -> list[PowerApp]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if top is not None:
            params["$top"] = top
        if skiptoken:
            params["$skiptoken"] = skiptoken
        items = self._collect_paginated(
            f"powerapps/environments/{environment_id}/apps",
            params=params,
            next_link_field="@odata.nextLink",
        )
        return [PowerApp.model_validate(o) for o in items]

    def list_app_versions(
        self,
        environment_id: str,
        app_id: str,
        *,
        top: int | None = None,
        skiptoken: str | None = None,
    ) -> AppVersionPage:
        """List versions for a Power App."""

        params = self._with_api_version()
        if top is not None:
            params["$top"] = top
        if skiptoken:
            params["$skiptoken"] = skiptoken
        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apps/{app_id}/versions",
            params=params,
        )
        payload = self._parse_response_dict(resp)
        raw_versions = payload.get("value")
        versions = (
            [AppVersion.model_validate(obj) for obj in cast(list[dict[str, Any]], raw_versions)]
            if isinstance(raw_versions, list)
            else []
        )
        next_link = cast(str | None, payload.get("nextLink"))
        continuation = cast(str | None, payload.get("continuationToken"))
        return AppVersionPage(versions, next_link, continuation)

    def restore_app(
        self, environment_id: str, app_id: str, payload: dict[str, Any]
    ) -> OperationHandle:
        """Restore an app to a specified version or target environment."""

        return self._post_operation(
            f"powerapps/environments/{environment_id}/apps/{app_id}:restore",
            body=payload,
        )

    def publish_app(
        self, environment_id: str, app_id: str, payload: dict[str, Any]
    ) -> OperationHandle:
        """Publish an app version."""

        return self._post_operation(
            f"powerapps/environments/{environment_id}/apps/{app_id}:publish",
            body=payload,
        )

    def share_app(
        self, environment_id: str, app_id: str, payload: dict[str, Any]
    ) -> OperationHandle:
        """Share an app with additional principals."""

        return self._post_operation(
            f"powerapps/environments/{environment_id}/apps/{app_id}:share",
            body=payload,
        )

    def revoke_app_share(
        self, environment_id: str, app_id: str, payload: dict[str, Any]
    ) -> OperationHandle:
        """Revoke previously granted app permissions."""

        return self._post_operation(
            f"powerapps/environments/{environment_id}/apps/{app_id}:revokeShare",
            body=payload,
        )

    def set_app_owner(
        self, environment_id: str, app_id: str, payload: dict[str, Any]
    ) -> OperationHandle:
        """Assign a new owner for an app."""

        return self._post_operation(
            f"powerapps/environments/{environment_id}/apps/{app_id}:setOwner",
            body=payload,
        )

    def list_app_permissions(
        self, environment_id: str, app_id: str
    ) -> list[AppPermissionAssignment]:
        """List permissions granted to principals for an app."""

        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apps/{app_id}/permissions",
            params=self._with_api_version(),
        )
        payload = self._parse_response_dict(resp)
        assignments = payload.get("value")
        if not isinstance(assignments, list):
            return []
        return [
            AppPermissionAssignment.model_validate(obj)
            for obj in cast(list[dict[str, Any]], assignments)
        ]

    def list_cloud_flows(self, environment_id: str, **filters: Any) -> list[CloudFlow]:
        params: dict[str, Any] = {"api-version": self.api_version}
        params.update({k: v for k, v in filters.items() if v is not None})
        items = self._collect_paginated(
            f"powerautomate/environments/{environment_id}/cloudFlows",
            params=params,
            next_link_field="@odata.nextLink",
        )
        return [CloudFlow.model_validate(o) for o in items]

    def get_cloud_flow(self, environment_id: str, flow_id: str) -> CloudFlow:
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}",
            params=self._with_api_version(),
        )
        return CloudFlow.model_validate(resp.json())

    def update_cloud_flow_state(
        self, environment_id: str, flow_id: str, payload: dict[str, Any]
    ) -> CloudFlow:
        resp = self.http.patch(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return CloudFlow.model_validate(resp.json())

    def delete_cloud_flow(self, environment_id: str, flow_id: str) -> None:
        self.http.delete(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}",
            params=self._with_api_version(),
        )

    def list_flow_actions(self, environment_id: str, **filters: Any) -> FlowActionList:
        params = self._with_api_version()
        params.update({k: v for k, v in filters.items() if v is not None})
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/flowActions",
            params=params,
        )
        payload = self._parse_response_dict(resp)
        return FlowActionList.model_validate(payload or {})

    def list_flow_runs(self, environment_id: str, workflow_id: str) -> list[FlowRun]:
        params = {"api-version": self.api_version, "workflowId": workflow_id}
        items = self._collect_paginated(
            f"powerautomate/environments/{environment_id}/flowRuns",
            params=params,
            next_link_field="workflowRun@odata.nextLink",
        )
        return [FlowRun.model_validate(o) for o in items]

    def list_cloud_flow_runs(
        self,
        environment_id: str,
        flow_id: str,
        *,
        status: str | None = None,
        trigger_name: str | None = None,
        top: int | None = None,
        continuation_token: str | None = None,
    ) -> FlowRunPage:
        params = self._with_api_version()
        if status:
            params["status"] = status
        if trigger_name:
            params["triggerName"] = trigger_name
        if top is not None:
            params["$top"] = top
        if continuation_token:
            params["$skiptoken"] = continuation_token
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs",
            params=params,
        )
        payload = self._parse_response_dict(resp)
        value = payload.get("value")
        runs = (
            [FlowRun.model_validate(obj) for obj in cast(list[dict[str, Any]], value)]
            if isinstance(value, list)
            else []
        )
        token = cast(str | None, resp.headers.get("x-ms-continuation-token"))
        if not token:
            token = cast(str | None, payload.get("continuationToken"))
        next_link = cast(str | None, payload.get("nextLink"))
        return FlowRunPage(runs, continuation_token=token, next_link=next_link)

    def trigger_cloud_flow_run(
        self, environment_id: str, flow_id: str, payload: dict[str, Any]
    ) -> FlowRun:
        resp = self.http.post(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs",
            params=self._with_api_version(),
            json=payload,
        )
        if not resp.text:
            return FlowRun()
        return FlowRun.model_validate(resp.json())

    def get_cloud_flow_run(
        self, environment_id: str, flow_id: str, run_name: str
    ) -> FlowRun:
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs/{run_name}",
            params=self._with_api_version(),
        )
        return FlowRun.model_validate(resp.json())

    def resubmit_cloud_flow_run(
        self,
        environment_id: str,
        flow_id: str,
        run_name: str,
        payload: dict[str, Any] | None = None,
    ) -> FlowRun:
        resp = self.http.post(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs/{run_name}",
            params=self._with_api_version(),
            json=payload or {},
        )
        if not resp.text:
            return FlowRun()
        return FlowRun.model_validate(resp.json())

    def delete_cloud_flow_run(
        self, environment_id: str, flow_id: str, run_name: str
    ) -> None:
        self.http.delete(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs/{run_name}",
            params=self._with_api_version(),
        )

    def cancel_cloud_flow_run(
        self, environment_id: str, flow_id: str, run_name: str
    ) -> None:
        self.http.post(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs/{run_name}:cancel",
            params=self._with_api_version(),
        )

    def get_cloud_flow_run_diagnostics(
        self, environment_id: str, flow_id: str, run_name: str
    ) -> FlowRunDiagnostics:
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}/runs/{run_name}/diagnostics",
            params=self._with_api_version(),
        )
        return FlowRunDiagnostics.model_validate(resp.json())

    def _collect_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        next_link_field: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_path: str | None = path
        next_params: dict[str, Any] | None = params

        while next_path:
            resp = self.http.get(next_path, params=next_params)
            payload = cast(dict[str, Any], resp.json()) if resp.text else {}
            values = cast(list[dict[str, Any]], payload.get("value", []))
            results.extend(values)

            link = payload.get(next_link_field)
            if not link:
                break
            link_str = cast(str, link)
            parsed = urlparse(link_str)
            if parsed.scheme and parsed.netloc:
                next_path = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            else:
                next_path = parsed.path.lstrip("/") or None
            query_items = parse_qsl(parsed.query, keep_blank_values=True)
            next_params = dict(query_items) if query_items else None

        return results
