from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any, cast
from urllib.parse import parse_qsl, urlparse

from ..http_client import HttpClient
from ..models.power_platform import CloudFlow, EnvironmentSummary, FlowRun, PowerApp

DEFAULT_API_VERSION = "2022-03-01-preview"


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

    def list_cloud_flows(self, environment_id: str, **filters: Any) -> list[CloudFlow]:
        params: dict[str, Any] = {"api-version": self.api_version}
        params.update({k: v for k, v in filters.items() if v is not None})
        items = self._collect_paginated(
            f"powerautomate/environments/{environment_id}/cloudFlows",
            params=params,
            next_link_field="@odata.nextLink",
        )
        return [CloudFlow.model_validate(o) for o in items]

    def list_flow_runs(self, environment_id: str, workflow_id: str) -> list[FlowRun]:
        params = {"api-version": self.api_version, "workflowId": workflow_id}
        items = self._collect_paginated(
            f"powerautomate/environments/{environment_id}/flowRuns",
            params=params,
            next_link_field="workflowRun@odata.nextLink",
        )
        return [FlowRun.model_validate(o) for o in items]

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
