"""Client helpers for Policy Data Loss Prevention management APIs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx

from ..http_client import HttpClient
from ..models.policy import (
    AsyncOperation,
    ConnectorGroup,
    DataLossPreventionPolicy,
    PolicyAssignment,
)

DEFAULT_API_VERSION = "2023-10-01-preview"


@dataclass(frozen=True)
class PolicyOperationHandle:
    """Metadata returned when a policy operation is accepted."""

    operation_location: str | None
    operation: AsyncOperation | None = None

    @property
    def operation_id(self) -> str | None:
        """Return the trailing identifier from :attr:`operation_location`."""

        if self.operation_location:
            return self.operation_location.rstrip("/").split("/")[-1]
        if self.operation is not None:
            return self.operation.operation_id
        return None


@dataclass(frozen=True)
class PolicyPage:
    """Container for a page of data loss prevention policies."""

    policies: list[DataLossPreventionPolicy]
    next_link: str | None = None


class DataLossPreventionClient:
    """HTTP client for the Data Loss Prevention (DLP) policy APIs."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def close(self) -> None:
        """Close the underlying HTTP transport."""

        self.http.close()

    def __enter__(self) -> "DataLossPreventionClient":
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
            params.update(extra)
        return params

    @staticmethod
    def _parse_response_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            payload = resp.json()
        except Exception:  # pragma: no cover - defensive parsing guard
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _model_dump(obj: Any) -> dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
        if isinstance(obj, dict):
            return obj
        raise TypeError(f"Unsupported payload type: {type(obj)!r}")

    def _build_operation_handle(self, resp: httpx.Response) -> PolicyOperationHandle:
        payload = self._parse_response_dict(resp)
        operation = None
        if payload:
            operation = AsyncOperation.model_validate(payload)
        return PolicyOperationHandle(resp.headers.get("Operation-Location"), operation)

    def list_policies(
        self,
        *,
        top: int | None = None,
        skip: int | None = None,
    ) -> PolicyPage:
        """Return a page of DLP policies."""

        params: dict[str, Any] = {"api-version": self.api_version}
        if top is not None:
            params["$top"] = top
        if skip is not None:
            params["$skip"] = skip
        resp = self.http.get("policy/dataLossPreventionPolicies", params=params)
        data = self._parse_response_dict(resp)
        raw_items = data.get("value")
        policies: list[DataLossPreventionPolicy] = []
        if isinstance(raw_items, Iterable):
            for item in raw_items:
                if isinstance(item, dict):
                    policies.append(DataLossPreventionPolicy.model_validate(item))
        next_link = data.get("nextLink") if isinstance(data.get("nextLink"), str) else None
        return PolicyPage(policies, next_link)

    def get_policy(self, policy_id: str) -> DataLossPreventionPolicy:
        resp = self.http.get(
            f"policy/dataLossPreventionPolicies/{policy_id}",
            params=self._with_api_version(),
        )
        return DataLossPreventionPolicy.model_validate(resp.json())

    def create_policy(self, policy: DataLossPreventionPolicy | dict[str, Any]) -> PolicyOperationHandle:
        payload = self._model_dump(policy)
        resp = self.http.post(
            "policy/dataLossPreventionPolicies",
            params=self._with_api_version(),
            json=payload,
        )
        return self._build_operation_handle(resp)

    def update_policy(
        self,
        policy_id: str,
        policy: DataLossPreventionPolicy | dict[str, Any],
    ) -> PolicyOperationHandle:
        payload = self._model_dump(policy)
        resp = self.http.patch(
            f"policy/dataLossPreventionPolicies/{policy_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return self._build_operation_handle(resp)

    def delete_policy(self, policy_id: str) -> PolicyOperationHandle:
        resp = self.http.delete(
            f"policy/dataLossPreventionPolicies/{policy_id}",
            params=self._with_api_version(),
        )
        return self._build_operation_handle(resp)

    def list_connector_groups(self, policy_id: str) -> list[ConnectorGroup]:
        resp = self.http.get(
            f"policy/dataLossPreventionPolicies/{policy_id}/connectors",
            params=self._with_api_version(),
        )
        payload = self._parse_response_dict(resp)
        groups_raw = payload.get("value")
        groups: list[ConnectorGroup] = []
        if isinstance(groups_raw, Iterable):
            for item in groups_raw:
                if isinstance(item, dict):
                    groups.append(ConnectorGroup.model_validate(item))
        return groups

    def update_connector_groups(
        self,
        policy_id: str,
        groups: Iterable[ConnectorGroup | dict[str, Any]],
    ) -> PolicyOperationHandle:
        payload_groups = [self._model_dump(group) for group in groups]
        resp = self.http.patch(
            f"policy/dataLossPreventionPolicies/{policy_id}/connectors",
            params=self._with_api_version(),
            json={"groups": payload_groups},
        )
        return self._build_operation_handle(resp)

    def list_assignments(self, policy_id: str) -> list[PolicyAssignment]:
        resp = self.http.get(
            f"policy/dataLossPreventionPolicies/{policy_id}/assignments",
            params=self._with_api_version(),
        )
        payload = self._parse_response_dict(resp)
        assignments_raw = payload.get("value")
        assignments: list[PolicyAssignment] = []
        if isinstance(assignments_raw, Iterable):
            for item in assignments_raw:
                if isinstance(item, dict):
                    assignments.append(PolicyAssignment.model_validate(item))
        return assignments

    def assign_policy(
        self,
        policy_id: str,
        assignments: Iterable[PolicyAssignment | dict[str, Any]],
    ) -> PolicyOperationHandle:
        payload_assignments = [self._model_dump(item) for item in assignments]
        resp = self.http.post(
            f"policy/dataLossPreventionPolicies/{policy_id}/assignments",
            params=self._with_api_version(),
            json={"assignments": payload_assignments},
        )
        return self._build_operation_handle(resp)

    def remove_assignment(self, policy_id: str, assignment_id: str) -> PolicyOperationHandle:
        resp = self.http.delete(
            f"policy/dataLossPreventionPolicies/{policy_id}/assignments/{assignment_id}",
            params=self._with_api_version(),
        )
        return self._build_operation_handle(resp)

    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 600.0,
    ) -> AsyncOperation:
        """Poll an async operation until completion or timeout."""

        from ..utils.poller import poll_until

        done_states = {"succeeded", "failed", "canceled", "cancelled"}

        def get_status() -> dict[str, Any]:
            resp = self.http.get(operation_url)
            return self._parse_response_dict(resp)

        def is_done(status: dict[str, Any]) -> bool:
            value = str(status.get("status") or status.get("state") or "").lower()
            return value in done_states

        def get_progress(status: dict[str, Any]) -> int | None:
            for key in ("percentComplete", "progress", "percentage", "completionPercent"):
                raw = status.get(key)
                if isinstance(raw, (int, float)):
                    return int(raw)
            return None

        result = poll_until(
            get_status,
            is_done,
            get_progress,
            interval=interval,
            timeout=timeout,
        )
        return AsyncOperation.model_validate(result)


__all__ = [
    "DataLossPreventionClient",
    "PolicyOperationHandle",
    "PolicyPage",
    "DEFAULT_API_VERSION",
]
