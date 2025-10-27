from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import httpx

from ..http_client import HttpClient
from ..utils.poller import poll_until

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class GovernanceOperation:
    """Metadata returned by governance long-running operations.

    Attributes:
        operation_location: Absolute or relative URL to poll for completion.
        metadata: Parsed JSON payload returned by the initial request.
    """

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def resource_id(self) -> str | None:
        """Return the trailing identifier extracted from :attr:`operation_location`."""

        if self.metadata.get("id"):
            identifier = self.metadata["id"]
            if isinstance(identifier, str) and identifier:
                return identifier
        if not self.operation_location:
            return None
        return self.operation_location.rstrip("/").split("/")[-1]


class GovernanceClient:
    """Client for Power Platform governance APIs."""

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
            for key, value in extra.items():
                if value is not None:
                    params[key] = value
        return params

    @staticmethod
    def _parse_dict(resp: httpx.Response) -> dict[str, Any]:
        if not getattr(resp, "text", None):  # pragma: no cover - defensive fallback
            return {}
        try:
            payload = resp.json()
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
        return {}

    def _post_operation(
        self,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> GovernanceOperation:
        resp = self.http.post(path, params=params or self._with_api_version(), json=body)
        metadata = self._parse_dict(resp)
        return GovernanceOperation(resp.headers.get("Operation-Location"), metadata)

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> GovernanceClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def create_cross_tenant_connection_report(self, payload: dict[str, Any]) -> GovernanceOperation:
        """Submit a cross-tenant connection report request."""

        return self._post_operation("governance/crossTenantConnectionReports", body=payload)

    def list_cross_tenant_connection_reports(self) -> dict[str, Any]:
        resp = self.http.get(
            "governance/crossTenantConnectionReports",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())

    def get_cross_tenant_connection_report(self, report_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"governance/crossTenantConnectionReports/{report_id}",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())

    def wait_for_report(
        self,
        report_id: str,
        *,
        interval: float = 5.0,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        """Poll the service until a cross-tenant report completes."""

        def _is_done(payload: dict[str, Any]) -> bool:
            status = str(payload.get("status", "")).lower()
            if not status:
                return False
            return status not in {
                "accepted",
                "running",
                "notstarted",
                "not started",
                "inprogress",
                "in progress",
                "queued",
                "pending",
            }

        return poll_until(
            lambda: self.get_cross_tenant_connection_report(report_id),
            _is_done,
            interval=interval,
            timeout=timeout,
        )

    def create_rule_based_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.post(
            "governance/ruleBasedPolicies",
            params=self._with_api_version(),
            json=payload,
        )
        return cast(dict[str, Any], resp.json())

    def list_rule_based_policies(self) -> dict[str, Any]:
        resp = self.http.get(
            "governance/ruleBasedPolicies",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())

    def get_rule_based_policy(self, policy_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"governance/ruleBasedPolicies/{policy_id}",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())

    def update_rule_based_policy(self, policy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.patch(
            f"governance/ruleBasedPolicies/{policy_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return cast(dict[str, Any], resp.json())

    def create_environment_group_assignment(
        self, policy_id: str, environment_group_id: str
    ) -> GovernanceOperation:
        return self._post_operation(
            f"governance/ruleBasedPolicies/{policy_id}/assignments/environmentGroups/{environment_group_id}",
        )

    def create_environment_assignment(self, policy_id: str, environment_id: str) -> GovernanceOperation:
        return self._post_operation(
            f"governance/ruleBasedPolicies/{policy_id}/assignments/environments/{environment_id}",
        )

    def list_assignments_by_policy(self, policy_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"governance/ruleBasedPolicies/{policy_id}/assignments",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())

    def list_rule_assignments(
        self,
        *,
        environment_id: str | None = None,
        environment_group_id: str | None = None,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        params = self._with_api_version(
            {
                "environmentId": environment_id,
                "environmentGroupId": environment_group_id,
                "policyId": policy_id,
            }
        )
        resp = self.http.get(
            "governance/ruleBasedPolicies/assignments",
            params=params,
        )
        return cast(dict[str, Any], resp.json())

    def list_assignments_by_environment_group(self, environment_group_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"governance/ruleBasedPolicies/assignments/byEnvironmentGroup/{environment_group_id}",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())

    def list_assignments_by_environment(self, environment_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"governance/ruleBasedPolicies/assignments/byEnvironment/{environment_id}",
            params=self._with_api_version(),
        )
        return cast(dict[str, Any], resp.json())


__all__ = [
    "DEFAULT_API_VERSION",
    "GovernanceClient",
    "GovernanceOperation",
]
