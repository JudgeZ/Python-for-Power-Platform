from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from ..http_client import HttpClient
from ..models.app_management import (
    ApplicationPackageOperation,
    ApplicationPackageSummary,
)

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class ApplicationOperationHandle:
    """Metadata returned when creating an application package operation."""

    operation_location: str | None
    metadata: ApplicationPackageOperation | None

    @property
    def operation_id(self) -> str | None:
        """Return the trailing identifier from :attr:`operation_location`."""

        if self.operation_location:
            return self.operation_location.rstrip("/").split("/")[-1]
        if self.metadata and self.metadata.operation_id:
            return self.metadata.operation_id
        return None


class AppManagementClient:
    """Client for the Power Platform application management APIs."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        *,
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
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_operation(data: dict[str, Any]) -> ApplicationPackageOperation | None:
        try:
            return ApplicationPackageOperation.model_validate(data)
        except ValidationError:
            return None

    def _post_operation(
        self,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApplicationOperationHandle:
        resp = self.http.post(path, params=params or self._with_api_version(), json=body)
        payload = self._parse_response_dict(resp)
        return ApplicationOperationHandle(
            resp.headers.get("Operation-Location"),
            self._parse_operation(payload),
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> AppManagementClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def list_tenant_packages(self) -> list[ApplicationPackageSummary]:
        """Return application packages available at the tenant scope."""

        resp = self.http.get(
            "appmanagement/applicationPackages",
            params=self._with_api_version(),
        )
        data = self._parse_response_dict(resp)
        value = data.get("value")
        if not isinstance(value, list):
            return []
        return [
            ApplicationPackageSummary.model_validate(item)
            for item in value
            if isinstance(item, dict)
        ]

    def list_environment_packages(self, environment_id: str) -> list[ApplicationPackageSummary]:
        """Return application packages installed in a specific environment."""

        resp = self.http.get(
            f"appmanagement/environments/{environment_id}/applicationPackages",
            params=self._with_api_version(),
        )
        data = self._parse_response_dict(resp)
        value = data.get("value")
        if not isinstance(value, list):
            return []
        return [
            ApplicationPackageSummary.model_validate(item)
            for item in value
            if isinstance(item, dict)
        ]

    def install_application_package(
        self,
        package_id: str,
        environment_id: str,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> ApplicationOperationHandle:
        """Install a tenant application package into an environment."""

        body: dict[str, Any] = {
            "packageId": package_id,
            "environmentId": environment_id,
        }
        if parameters:
            body["parameters"] = parameters
        return self._post_operation(
            "appmanagement/applications/installApplicationPackage",
            body=body,
        )

    def install_environment_package(
        self,
        environment_id: str,
        unique_name: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> ApplicationOperationHandle:
        """Install an environment application package by unique name."""

        return self._post_operation(
            f"appmanagement/environments/{environment_id}/applicationPackages/{unique_name}/install",
            body=payload,
        )

    def upgrade_environment_package(
        self,
        environment_id: str,
        package_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> ApplicationOperationHandle:
        """Upgrade an environment application package."""

        return self._post_operation(
            f"appmanagement/environments/{environment_id}/applicationPackages/{package_id}:upgrade",
            body=payload,
        )

    def get_install_status(self, operation_id: str) -> ApplicationPackageOperation | None:
        """Fetch the status for a tenant application package install operation."""

        resp = self.http.get(
            f"appmanagement/applications/installStatuses/{operation_id}",
            params=self._with_api_version(),
        )
        return self._parse_operation(self._parse_response_dict(resp))

    def get_environment_operation_status(
        self, environment_id: str, operation_id: str
    ) -> ApplicationPackageOperation | None:
        """Fetch the status for an environment application package operation."""

        resp = self.http.get(
            f"appmanagement/environments/{environment_id}/operations/{operation_id}",
            params=self._with_api_version(),
        )
        return self._parse_operation(self._parse_response_dict(resp))

    def wait_for_operation(
        self,
        handle: ApplicationOperationHandle,
        *,
        environment_id: str | None = None,
        interval: float = 2.0,
        timeout: float = 600.0,
    ) -> ApplicationPackageOperation:
        """Poll an operation handle until completion or timeout."""

        from ..utils.poller import poll_until

        operation_url = handle.operation_location
        if not operation_url:
            operation_id = handle.operation_id
            if not operation_id:
                raise ValueError("Operation handle does not include a polling location.")
            if environment_id:
                operation_url = (
                    f"appmanagement/environments/{environment_id}/operations/{operation_id}"
                )
            else:
                operation_url = f"appmanagement/applications/installStatuses/{operation_id}"

        parsed = urlparse(operation_url)
        params = None if parsed.query else self._with_api_version()

        def get_status() -> dict[str, Any]:
            resp = self.http.get(operation_url, params=params)
            return self._parse_response_dict(resp)

        done_states = {"succeeded", "failed", "canceled", "cancelled"}

        def is_done(status: dict[str, Any]) -> bool:
            state = str(status.get("status") or "").lower()
            if state in done_states:
                return True
            return bool(status.get("percentComplete") == 100)

        def get_progress(status: dict[str, Any]) -> int | None:
            value = status.get("percentComplete")
            if isinstance(value, int | float):
                return int(value)
            return None

        result = poll_until(
            get_status,
            is_done,
            get_progress,
            interval=interval,
            timeout=timeout,
        )
        operation = self._parse_operation(result)
        if operation is None:
            raise ValueError("Unable to parse operation status response.")
        return operation


__all__ = [
    "AppManagementClient",
    "ApplicationOperationHandle",
    "DEFAULT_API_VERSION",
]
