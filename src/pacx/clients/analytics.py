from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import parse_qsl, urlparse

import httpx

from ..http_client import HttpClient
from ..models.analytics import (
    AdvisorAction,
    AdvisorActionRequest,
    AdvisorActionResponse,
    AdvisorRecommendationAcknowledgement,
    AdvisorRecommendationDetail,
    AdvisorRecommendationOperationStatus,
    AdvisorRecommendationResource,
    AdvisorRecommendationStatus,
    AdvisorScenario,
    RecommendationActionPayload,
)

DEFAULT_ANALYTICS_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class RecommendationResourcePage:
    """Container for a single page of scenario resources."""

    resources: list[AdvisorRecommendationResource]
    next_link: str | None = None
    skip_token: str | None = None


@dataclass(frozen=True)
class RecommendationOperationHandle:
    """Metadata returned by acknowledge and dismiss operations."""

    operation_location: str | None
    acknowledgement: AdvisorRecommendationAcknowledgement | None

    @property
    def operation_id(self) -> str | None:
        """Best-effort operation identifier extracted from the handle."""

        if self.acknowledgement and self.acknowledgement.operation_id:
            return self.acknowledgement.operation_id
        if not self.operation_location:
            return None
        parsed = urlparse(self.operation_location)
        path = parsed.path.rstrip("/").split("/")
        if not path:
            return None
        candidate = path[-1]
        return candidate or None


class AnalyticsClient:
    """Client for Advisor Recommendations analytics APIs."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        *,
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_ANALYTICS_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def close(self) -> None:
        """Close the underlying HTTP session."""

        self.http.close()

    def __enter__(self) -> AnalyticsClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        self.close()

    def _with_api_version(self, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        merged = {"api-version": self.api_version}
        if params:
            merged.update(params)
        return merged

    @staticmethod
    def _as_dict(resp: httpx.Response) -> dict[str, Any]:
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        if isinstance(data, dict):
            return cast(dict[str, Any], data)
        return {}

    def list_scenarios(self) -> list[AdvisorScenario]:
        resp = self.http.get(
            "analytics/advisorRecommendations/scenarios", params=self._with_api_version()
        )
        data = resp.json()
        if not isinstance(data, Sequence):
            return []
        return [AdvisorScenario.model_validate(item) for item in data]

    def list_actions(self, scenario: str) -> list[AdvisorAction]:
        resp = self.http.get(
            f"analytics/advisorRecommendations/{scenario}/actions",
            params=self._with_api_version(),
        )
        payload = resp.json()
        if not isinstance(payload, Sequence):
            return []
        return [AdvisorAction.model_validate(item) for item in payload]

    def get_action_schema(self, scenario: str, action_name: str) -> dict[str, Any]:
        resp = self.http.get(
            f"analytics/advisorRecommendations/{scenario}/actionmetadata/{action_name}",
            params=self._with_api_version(),
        )
        return self._as_dict(resp)

    def list_resources(
        self,
        scenario: str,
        *,
        top: int | None = None,
        skiptoken: str | None = None,
    ) -> RecommendationResourcePage:
        params: dict[str, Any] = {}
        if top is not None:
            params["$top"] = top
        if skiptoken is not None:
            params["$skiptoken"] = skiptoken
        resp = self.http.get(
            f"analytics/advisorRecommendations/{scenario}/resources",
            params=self._with_api_version(params),
        )
        data = self._as_dict(resp)
        raw_items = data.get("value")
        if not isinstance(raw_items, Sequence):
            items: list[AdvisorRecommendationResource] = []
        else:
            items = [AdvisorRecommendationResource.model_validate(obj) for obj in raw_items]
        next_link = data.get("@odata.nextLink")
        skip = None
        if isinstance(next_link, str):
            parsed = urlparse(next_link)
            if parsed.query:
                params = dict(parse_qsl(parsed.query))
                skip = params.get("$skiptoken") or params.get("$skipToken")
        return RecommendationResourcePage(
            items, next_link=cast(str | None, next_link), skip_token=skip
        )

    def iter_resources(
        self, scenario: str, *, top: int | None = None
    ) -> Iterable[list[AdvisorRecommendationResource]]:
        skiptoken: str | None = None
        while True:
            page = self.list_resources(scenario, top=top, skiptoken=skiptoken)
            yield page.resources
            if not page.next_link or not page.skip_token:
                break
            skiptoken = page.skip_token

    def list_recommendations(self, scenario: str) -> list[AdvisorRecommendationDetail]:
        resp = self.http.get(
            f"analytics/advisorRecommendations/{scenario}/recommendations",
            params=self._with_api_version(),
        )
        data = self._as_dict(resp)
        raw_items = data.get("value")
        if not isinstance(raw_items, Sequence):
            return []
        return [AdvisorRecommendationDetail.model_validate(obj) for obj in raw_items]

    def get_recommendation(
        self, scenario: str, recommendation_id: str
    ) -> AdvisorRecommendationDetail:
        resp = self.http.get(
            f"analytics/advisorRecommendations/{scenario}/recommendations/{recommendation_id}",
            params=self._with_api_version(),
        )
        return AdvisorRecommendationDetail.model_validate(resp.json())

    @staticmethod
    def _prepare_payload(
        payload: RecommendationActionPayload | Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        if payload is None:
            return None
        if isinstance(payload, RecommendationActionPayload):
            data = payload.to_payload()
            return data or None
        if isinstance(payload, Mapping):
            model = RecommendationActionPayload.model_validate(payload)
            data = model.to_payload()
            return data or None
        raise TypeError("payload must be RecommendationActionPayload, mapping, or None")

    def acknowledge_recommendation(
        self,
        scenario: str,
        recommendation_id: str,
        payload: RecommendationActionPayload | Mapping[str, Any] | None = None,
    ) -> RecommendationOperationHandle:
        body = self._prepare_payload(payload)
        resp = self.http.post(
            f"analytics/advisorRecommendations/{scenario}/recommendations/{recommendation_id}:acknowledge",
            params=self._with_api_version(),
            json=body,
        )
        ack_data = self._as_dict(resp)
        ack = AdvisorRecommendationAcknowledgement.model_validate(ack_data) if ack_data else None
        return RecommendationOperationHandle(resp.headers.get("Operation-Location"), ack)

    def dismiss_recommendation(
        self,
        scenario: str,
        recommendation_id: str,
        payload: RecommendationActionPayload | Mapping[str, Any] | None = None,
    ) -> RecommendationOperationHandle:
        body = self._prepare_payload(payload)
        resp = self.http.post(
            f"analytics/advisorRecommendations/{scenario}/recommendations/{recommendation_id}:dismiss",
            params=self._with_api_version(),
            json=body,
        )
        ack_data = self._as_dict(resp)
        ack = AdvisorRecommendationAcknowledgement.model_validate(ack_data) if ack_data else None
        return RecommendationOperationHandle(resp.headers.get("Operation-Location"), ack)

    def get_recommendation_status(
        self, scenario: str, recommendation_id: str
    ) -> AdvisorRecommendationStatus:
        resp = self.http.get(
            f"analytics/advisorRecommendations/{scenario}/recommendations/{recommendation_id}/status",
            params=self._with_api_version(),
        )
        return AdvisorRecommendationStatus.model_validate(resp.json())

    def get_operation_status(self, operation_id: str) -> AdvisorRecommendationOperationStatus:
        resp = self.http.get(
            f"analytics/advisorRecommendations/operations/{operation_id}",
            params=self._with_api_version(),
        )
        return AdvisorRecommendationOperationStatus.model_validate(resp.json())

    def _operation_request(self, location: str) -> tuple[str, dict[str, Any] | None]:
        parsed = urlparse(location)
        if parsed.scheme in {"http", "https"}:
            if parsed.query:
                return location, None
            return location, {"api-version": self.api_version}
        path, _, query = location.partition("?")
        params = dict(parse_qsl(query)) if query else {}
        if "api-version" not in params:
            params["api-version"] = self.api_version
        normalized_path = path.lstrip("/")
        if not normalized_path.startswith("analytics/"):
            normalized_path = (
                f"analytics/advisorRecommendations/operations/{normalized_path}".rstrip("/")
            )
        return normalized_path, params

    def wait_for_operation(
        self,
        handle: RecommendationOperationHandle | str,
        *,
        interval: float = 2.0,
        timeout: float = 300.0,
    ) -> AdvisorRecommendationOperationStatus:
        from ..utils.poller import poll_until

        if isinstance(handle, RecommendationOperationHandle):
            location = handle.operation_location
            operation_id = handle.operation_id
        else:
            location = str(handle)
            operation_id = None

        if location:
            target, params = self._operation_request(location)
        elif operation_id:
            target = f"analytics/advisorRecommendations/operations/{operation_id}"
            params = self._with_api_version()
        else:  # pragma: no cover - defensive guard
            raise ValueError("Operation handle must include a location or identifier")

        def get_status() -> dict[str, Any]:
            response = self.http.get(target, params=params)
            return self._as_dict(response)

        def is_done(status: dict[str, Any]) -> bool:
            state = str(status.get("status", "")).lower()
            return state in {"succeeded", "failed", "canceled", "cancelled"}

        result = poll_until(get_status, is_done, interval=interval, timeout=timeout)
        return AdvisorRecommendationOperationStatus.model_validate(result)

    def execute_action(
        self,
        action_name: str,
        payload: AdvisorActionRequest | Mapping[str, Any],
    ) -> AdvisorActionResponse:
        if isinstance(payload, AdvisorActionRequest):
            body = payload.to_payload()
        elif isinstance(payload, Mapping):
            body = AdvisorActionRequest.model_validate(payload).to_payload()
        else:  # pragma: no cover - defensive guard
            raise TypeError("payload must be AdvisorActionRequest or mapping")
        resp = self.http.post(
            f"analytics/actions/{action_name}",
            params=self._with_api_version(),
            json=body,
        )
        return AdvisorActionResponse.model_validate(resp.json())


__all__ = [
    "AnalyticsClient",
    "RecommendationOperationHandle",
    "RecommendationResourcePage",
]
