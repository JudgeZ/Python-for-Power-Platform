from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx
from pydantic import ValidationError

from ..http_client import HttpClient
from ..models.power_platform import (
    AppListPage,
    AppPermissionAssignment,
    AppSummary,
    AppVersionList,
    RevokeShareRequest,
    SetOwnerRequest,
    ShareAppRequest,
    SharePrincipal,
)

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class AdminOperationHandle:
    """Metadata for asynchronous Power Apps admin operations."""

    operation_location: str | None
    retry_after: int | None = None


class PowerAppsAdminClient:
    """Client for Power Apps administration endpoints."""

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
            params.update({k: v for k, v in extra.items() if v is not None})
        return params

    @staticmethod
    def _parse_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _map_app(obj: Any) -> AppSummary | None:
        if not isinstance(obj, dict):
            return None
        return AppSummary.model_validate(obj)

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> PowerAppsAdminClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # Listing helpers -----------------------------------------------------------------

    def list_apps(
        self,
        environment_id: str,
        *,
        top: int | None = None,
        continuation_token: str | None = None,
    ) -> AppListPage:
        params = {
            "$top": top,
            "$skiptoken": continuation_token,
        }
        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apps",
            params=self._with_api_version(params),
        )
        data = self._parse_dict(resp)
        return AppListPage.model_validate(data or {})

    def get_app(self, environment_id: str, app_id: str) -> AppSummary:
        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apps/{app_id}",
            params=self._with_api_version(),
        )
        return AppSummary.model_validate(self._parse_dict(resp))

    def list_app_versions(
        self,
        environment_id: str,
        app_id: str,
        *,
        top: int | None = None,
        continuation_token: str | None = None,
    ) -> AppVersionList:
        params = {
            "$top": top,
            "$skiptoken": continuation_token,
        }
        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apps/{app_id}/versions",
            params=self._with_api_version(params),
        )
        data = self._parse_dict(resp)
        return AppVersionList.model_validate(data or {})

    def list_permissions(
        self,
        environment_id: str,
        app_id: str,
    ) -> list[AppPermissionAssignment]:
        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apps/{app_id}/permissions",
            params=self._with_api_version(),
        )
        data = self._parse_dict(resp)
        permissions: list[AppPermissionAssignment] = []
        for item in data.get("value", []) if isinstance(data, dict) else []:
            if isinstance(item, dict):
                permissions.append(AppPermissionAssignment.model_validate(item))
        return permissions

    # Mutation helpers ----------------------------------------------------------------

    def _operation_handle(self, resp: httpx.Response) -> AdminOperationHandle:
        retry_after = resp.headers.get("Retry-After")
        retry: int | None = None
        if isinstance(retry_after, str) and retry_after.isdigit():
            retry = int(retry_after)
        return AdminOperationHandle(resp.headers.get("Operation-Location"), retry)

    def restore_app(
        self,
        environment_id: str,
        app_id: str,
        payload: dict[str, Any],
    ) -> AdminOperationHandle:
        resp = self.http.post(
            f"powerapps/environments/{environment_id}/apps/{app_id}:restore",
            params=self._with_api_version(),
            json=payload,
        )
        return self._operation_handle(resp)

    def publish_app(
        self,
        environment_id: str,
        app_id: str,
        payload: dict[str, Any],
    ) -> AdminOperationHandle:
        resp = self.http.post(
            f"powerapps/environments/{environment_id}/apps/{app_id}:publish",
            params=self._with_api_version(),
            json=payload,
        )
        return self._operation_handle(resp)

    def share_app(
        self,
        environment_id: str,
        app_id: str,
        request: ShareAppRequest,
    ) -> AdminOperationHandle:
        resp = self.http.post(
            f"powerapps/environments/{environment_id}/apps/{app_id}:share",
            params=self._with_api_version(),
            json=request.to_payload(),
        )
        return self._operation_handle(resp)

    def revoke_share(
        self,
        environment_id: str,
        app_id: str,
        request: RevokeShareRequest,
    ) -> AdminOperationHandle:
        resp = self.http.post(
            f"powerapps/environments/{environment_id}/apps/{app_id}:revokeShare",
            params=self._with_api_version(),
            json=request.to_payload(),
        )
        return self._operation_handle(resp)

    def set_owner(
        self,
        environment_id: str,
        app_id: str,
        request: SetOwnerRequest,
    ) -> AdminOperationHandle:
        resp = self.http.post(
            f"powerapps/environments/{environment_id}/apps/{app_id}:setOwner",
            params=self._with_api_version(),
            json=request.to_payload(),
        )
        return self._operation_handle(resp)

    @staticmethod
    def share_principals_from_dict(data: Iterable[dict[str, Any]]) -> list[SharePrincipal]:
        """Helper for building share principals from raw dictionaries."""

        principals: list[SharePrincipal] = []
        for item in data:
            try:
                principals.append(SharePrincipal.model_validate(item))
            except ValidationError:  # pragma: no cover - validation error
                continue
        return principals


__all__ = ["PowerAppsAdminClient", "AdminOperationHandle"]
