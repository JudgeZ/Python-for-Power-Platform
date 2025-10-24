from __future__ import annotations

from typing import Any

from ..http_client import HttpClient
from ..models.power_platform import CloudFlow, EnvironmentSummary, FlowRun, PowerApp

DEFAULT_API_VERSION = "2022-03-01-preview"


class PowerPlatformClient:
    """Client for Power Platform Admin & product APIs."""

    def __init__(
        self,
        token_getter,
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def list_environments(self) -> list[EnvironmentSummary]:
        resp = self.http.get(
            "environmentmanagement/environments", params={"api-version": self.api_version}
        )
        data = resp.json()
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
        return resp.json()

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
        resp = self.http.get(f"powerapps/environments/{environment_id}/apps", params=params)
        data = resp.json()
        return [PowerApp.model_validate(o) for o in data.get("value", [])]

    def list_cloud_flows(self, environment_id: str, **filters: Any) -> list[CloudFlow]:
        params: dict[str, Any] = {"api-version": self.api_version}
        params.update({k: v for k, v in filters.items() if v is not None})
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows", params=params
        )
        data = resp.json() if resp.text else {"value": []}
        return [CloudFlow.model_validate(o) for o in data.get("value", [])]

    def list_flow_runs(self, environment_id: str, workflow_id: str) -> list[FlowRun]:
        params = {"api-version": self.api_version, "workflowId": workflow_id}
        resp = self.http.get(f"powerautomate/environments/{environment_id}/flowRuns", params=params)
        data = resp.json() if resp.text else {"value": []}
        return [FlowRun.model_validate(o) for o in data.get("value", [])]
