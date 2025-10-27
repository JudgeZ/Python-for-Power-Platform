"""Client for the Power Platform user management APIs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import httpx

from ..http_client import HttpClient
from ..models.user_management import (
    AdminRoleAssignmentList,
    AsyncOperationStatus,
    RemoveAdminRoleRequest,
)

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class UserManagementOperationHandle:
    """Metadata returned by async user management operations."""

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def operation_id(self) -> str | None:
        """Return the trailing identifier from the operation URL."""

        if not self.operation_location:
            return None
        return self.operation_location.rstrip("/").split("/")[-1]


class UserManagementClient:
    """HTTP client for user admin role assignments."""

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
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> UserManagementClient:
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
            data = resp.json()
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    def _post_operation(
        self,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> UserManagementOperationHandle:
        resp = self.http.post(path, params=params or self._with_api_version(), json=body)
        payload = self._parse_response_dict(resp)
        return UserManagementOperationHandle(resp.headers.get("Operation-Location"), payload)

    def apply_admin_role(self, user_id: str) -> UserManagementOperationHandle:
        """Apply the default admin role to a user."""

        return self._post_operation(f"usermanagement/users/{user_id}:applyAdminRole")

    def remove_admin_role(
        self, user_id: str, payload: RemoveAdminRoleRequest | str
    ) -> UserManagementOperationHandle:
        """Remove a specific admin role assignment from the user."""

        if isinstance(payload, str):
            body = RemoveAdminRoleRequest(roleDefinitionId=payload)
        else:
            body = payload
        return self._post_operation(
            f"usermanagement/users/{user_id}:removeAdminRole",
            body=body.model_dump(by_alias=True, exclude_none=True),
        )

    def list_admin_roles(self, user_id: str) -> AdminRoleAssignmentList:
        """List admin roles currently assigned to a user."""

        resp = self.http.get(
            f"usermanagement/users/{user_id}/adminRoles",
            params=self._with_api_version(),
        )
        data = self._parse_response_dict(resp)
        return AdminRoleAssignmentList.model_validate(data)

    def get_operation(self, operation_id: str) -> AsyncOperationStatus:
        """Fetch status for a user management operation by identifier."""

        resp = self.http.get(
            f"usermanagement/operations/{operation_id}",
            params=self._with_api_version(),
        )
        data = self._parse_response_dict(resp)
        return AsyncOperationStatus.model_validate(data)

    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 600.0,
    ) -> AsyncOperationStatus:
        """Poll an operation URL until it reaches a terminal state."""

        from ..utils.poller import poll_until

        done_states = {"Succeeded", "Failed", "Canceled"}

        def get_status() -> dict[str, Any]:
            params = None if "?" in operation_url else self._with_api_version()
            resp = self.http.get(operation_url, params=params)
            return self._parse_response_dict(resp)

        def is_done(payload: dict[str, Any]) -> bool:
            status = AsyncOperationStatus.model_validate(payload)
            if status.status is None:
                return False
            return status.status in done_states

        def to_progress(payload: dict[str, Any]) -> int | None:
            status = AsyncOperationStatus.model_validate(payload)
            pct = status.percent_complete
            return int(pct) if pct is not None else None

        result = poll_until(
            get_status=get_status,
            is_done=is_done,
            get_progress=to_progress,
            interval=interval,
            timeout=timeout,
        )
        return AsyncOperationStatus.model_validate(result)


__all__ = [
    "DEFAULT_API_VERSION",
    "UserManagementClient",
    "UserManagementOperationHandle",
]
