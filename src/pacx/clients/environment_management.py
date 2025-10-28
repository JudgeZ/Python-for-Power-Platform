from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx

from ..http_client import HttpClient
from ..models.environment_management import (
    EnvironmentBackupRequest,
    EnvironmentCopyRequest,
    EnvironmentCreateRequest,
    EnvironmentLifecycleOperation,
    EnvironmentListPage,
    EnvironmentResetRequest,
    EnvironmentRestoreRequest,
)
from ..models.power_platform import EnvironmentSummary

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class EnvironmentOperationHandle:
    """Metadata for asynchronous environment management operations."""

    operation_location: str | None
    retry_after: int | None = None
    operation: EnvironmentLifecycleOperation | None = None


class EnvironmentManagementClient:
    """Client for Power Platform environment management endpoints."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        *,
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> EnvironmentManagementClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # Internal helpers -----------------------------------------------------------------

    def _with_api_version(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            params.update({key: value for key, value in extra.items() if value is not None})
        return params

    @staticmethod
    def _parse_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.content:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive guard
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _retry_after(resp: httpx.Response) -> int | None:
        header = resp.headers.get("Retry-After")
        if isinstance(header, str) and header.isdigit():
            return int(header)
        return None

    def _operation_handle(
        self, resp: httpx.Response, data: dict[str, Any] | None = None
    ) -> EnvironmentOperationHandle:
        operation = None
        if data:
            operation = EnvironmentLifecycleOperation.model_validate(data)
        return EnvironmentOperationHandle(
            resp.headers.get("Operation-Location"), self._retry_after(resp), operation
        )

    # Environment lifecycle -------------------------------------------------------------

    def list_environments(
        self, *, top: int | None = None, continuation_token: str | None = None
    ) -> EnvironmentListPage:
        params = {"$top": top, "$skiptoken": continuation_token}
        resp = self.http.get(
            "environmentmanagement/environments",
            params=self._with_api_version(params),
        )
        data = self._parse_dict(resp)
        return EnvironmentListPage.model_validate(data or {})

    def create_environment(
        self,
        request: EnvironmentCreateRequest,
        *,
        validate_only: bool | None = None,
    ) -> EnvironmentOperationHandle:
        params = {"validateOnly": validate_only}
        resp = self.http.post(
            "environmentmanagement/environments",
            params=self._with_api_version(params),
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def get_environment(self, environment_id: str) -> EnvironmentSummary:
        resp = self.http.get(
            f"environmentmanagement/environments/{environment_id}",
            params=self._with_api_version(),
        )
        data = self._parse_dict(resp)
        return EnvironmentSummary.model_validate(data or {})

    def delete_environment(
        self,
        environment_id: str,
        *,
        validate_only: bool | None = None,
    ) -> EnvironmentOperationHandle:
        params = {"ValidateOnly": validate_only}
        resp = self.http.delete(
            f"environmentmanagement/environments/{environment_id}",
            params=self._with_api_version(params),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def copy_environment(
        self,
        environment_id: str,
        request: EnvironmentCopyRequest,
    ) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environments/{environment_id}:copy",
            params=self._with_api_version(),
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def reset_environment(
        self,
        environment_id: str,
        request: EnvironmentResetRequest,
    ) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environments/{environment_id}:reset",
            params=self._with_api_version(),
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def backup_environment(
        self,
        environment_id: str,
        request: EnvironmentBackupRequest,
    ) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environments/{environment_id}:backup",
            params=self._with_api_version(),
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def restore_environment(
        self,
        environment_id: str,
        request: EnvironmentRestoreRequest,
    ) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environments/{environment_id}:restore",
            params=self._with_api_version(),
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def list_operations(self, environment_id: str) -> list[EnvironmentLifecycleOperation]:
        resp = self.http.get(
            f"environmentmanagement/environments/{environment_id}/operations",
            params=self._with_api_version(),
        )
        data = self._parse_dict(resp)
        items = data.get("value") if isinstance(data, dict) else []
        operations: list[EnvironmentLifecycleOperation] = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    operations.append(EnvironmentLifecycleOperation.model_validate(item))
        return operations

    def get_operation(self, operation_id: str) -> EnvironmentLifecycleOperation:
        resp = self.http.get(
            f"environmentmanagement/operations/{operation_id}",
            params=self._with_api_version(),
        )
        data = self._parse_dict(resp)
        return EnvironmentLifecycleOperation.model_validate(data or {})

    # Environment groups ----------------------------------------------------------------

    def list_environment_groups(self) -> list[dict[str, Any]]:
        resp = self.http.get(
            "environmentmanagement/environmentGroups",
            params=self._with_api_version(),
        )
        data = self._parse_dict(resp)
        items = data.get("value") if isinstance(data, dict) else []
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    def create_environment_group(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.post(
            "environmentmanagement/environmentGroups",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_dict(resp)

    def get_environment_group(self, environment_group_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"environmentmanagement/environmentGroups/{environment_group_id}",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def update_environment_group(
        self, environment_group_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        resp = self.http.patch(
            f"environmentmanagement/environmentGroups/{environment_group_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_dict(resp)

    def delete_environment_group(self, environment_group_id: str) -> EnvironmentOperationHandle:
        resp = self.http.delete(
            f"environmentmanagement/environmentGroups/{environment_group_id}",
            params=self._with_api_version(),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def add_environment_to_group(
        self,
        environment_group_id: str,
        environment_id: str,
    ) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environmentGroups/{environment_group_id}/environments/{environment_id}/apply",
            params=self._with_api_version(),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def remove_environment_from_group(
        self,
        environment_group_id: str,
        environment_id: str,
    ) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environmentGroups/{environment_group_id}/environments/{environment_id}/revoke",
            params=self._with_api_version(),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    # Managed environments ---------------------------------------------------------------

    def enable_managed_environment(self, environment_id: str) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environments/{environment_id}/managedGovernance/enable",
            params=self._with_api_version(),
        )
        return self._operation_handle(resp, self._parse_dict(resp))

    def disable_managed_environment(self, environment_id: str) -> EnvironmentOperationHandle:
        resp = self.http.post(
            f"environmentmanagement/environments/{environment_id}/managedGovernance/disable",
            params=self._with_api_version(),
        )
        return self._operation_handle(resp, self._parse_dict(resp))


__all__ = ["EnvironmentManagementClient", "EnvironmentOperationHandle"]
