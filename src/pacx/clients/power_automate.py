from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any, cast

import httpx

from ..http_client import HttpClient
from ..models.power_automate import (
    CloudFlowPage,
    CloudFlowState,
    CloudFlowStatePatch,
)
from ..models.power_platform import CloudFlow

DEFAULT_API_VERSION = "2022-03-01-preview"
_CONTINUATION_HEADER = "x-ms-continuation-token"


class PowerAutomateClient:
    """Client focused on Power Automate (cloud flow) APIs."""

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

    def __enter__(self) -> PowerAutomateClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _with_api_version(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            params.update({k: v for k, v in extra.items() if v is not None})
        return params

    @staticmethod
    def _parse_response_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    def list_cloud_flows(
        self,
        environment_id: str,
        *,
        workflow_id: str | None = None,
        resource_id: str | None = None,
        created_by: str | None = None,
        owner_id: str | None = None,
        created_on_start_date: str | None = None,
        created_on_end_date: str | None = None,
        modified_on_start_date: str | None = None,
        modified_on_end_date: str | None = None,
        continuation_token: str | None = None,
    ) -> CloudFlowPage:
        """List cloud flows within an environment."""

        params = self._with_api_version(
            {
                "workflowId": workflow_id,
                "resourceId": resource_id,
                "createdBy": created_by,
                "ownerId": owner_id,
                "createdOnStartDate": created_on_start_date,
                "createdOnEndDate": created_on_end_date,
                "modifiedOnStartDate": modified_on_start_date,
                "modifiedOnEndDate": modified_on_end_date,
            }
        )
        headers: dict[str, str] | None = None
        if continuation_token:
            headers = {_CONTINUATION_HEADER: continuation_token}
        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows",
            params=params,
            headers=headers,
        )
        payload = self._parse_response_dict(resp)
        values = payload.get("value")
        flows = [
            CloudFlow.model_validate(obj)
            for obj in cast(list[dict[str, Any]], values or [])
            if isinstance(obj, dict)
        ]
        next_link = payload.get("nextLink") or payload.get("@odata.nextLink")
        token = resp.headers.get(_CONTINUATION_HEADER)
        return CloudFlowPage(
            flows=flows,
            next_link=cast(str | None, next_link),
            continuation_token=token,
        )

    def get_cloud_flow(self, environment_id: str, flow_id: str) -> CloudFlow:
        """Retrieve metadata for a single cloud flow."""

        resp = self.http.get(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}",
            params=self._with_api_version(),
        )
        return CloudFlow.model_validate(resp.json())

    def set_cloud_flow_state(
        self,
        environment_id: str,
        flow_id: str,
        state: CloudFlowState | CloudFlowStatePatch,
    ) -> CloudFlow:
        """Update the execution state for the specified cloud flow."""

        if isinstance(state, CloudFlowStatePatch):
            payload = state.to_payload()
        else:
            payload = CloudFlowStatePatch(state=state).to_payload()
        resp = self.http.patch(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return CloudFlow.model_validate(resp.json())

    def delete_cloud_flow(self, environment_id: str, flow_id: str) -> None:
        """Delete a cloud flow from the environment."""

        self.http.delete(
            f"powerautomate/environments/{environment_id}/cloudFlows/{flow_id}",
            params=self._with_api_version(),
        )


__all__ = ["PowerAutomateClient", "DEFAULT_API_VERSION"]
