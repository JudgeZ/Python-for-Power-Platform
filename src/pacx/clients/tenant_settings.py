"""Client for the Power Platform tenant settings surface."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, TypeVar

from pydantic import BaseModel

from ..http_client import HttpClient
from ..models.tenant_settings import (
    TenantFeatureAccessRequest,
    TenantFeatureControl,
    TenantFeatureControlList,
    TenantFeatureControlPatch,
    TenantSettings,
    TenantSettingsAccessRequest,
    TenantSettingsPatch,
)

DEFAULT_API_VERSION = "2024-03-01-preview"

PayloadModel = TypeVar("PayloadModel", bound=BaseModel)


@dataclass(frozen=True)
class TenantOperationResult:
    """Represents the outcome of a tenant settings mutation request."""

    resource: TenantSettings | TenantFeatureControl | None
    status_code: int
    operation_location: str | None

    @property
    def accepted(self) -> bool:
        """Return ``True`` when the server responded with HTTP 202."""

        return self.status_code == 202


class TenantSettingsClient:
    """Thin wrapper over the tenant settings REST endpoints."""

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

    def __enter__(self) -> TenantSettingsClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _params(self, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            params.update(extra)
        return params

    @staticmethod
    def _prepare_payload(payload: Mapping[str, Any] | PayloadModel | None) -> dict[str, Any]:
        if payload is None:
            return {}
        if isinstance(payload, BaseModel):
            return payload.model_dump(exclude_none=True, by_alias=True)
        return {str(key): value for key, value in payload.items()}

    def get_settings(self) -> TenantSettings:
        """Retrieve the current tenant configuration snapshot."""

        resp = self.http.get("tenantsettings", params=self._params())
        return TenantSettings.model_validate(resp.json())

    def update_settings(
        self,
        patch: Mapping[str, Any] | TenantSettingsPatch,
        *,
        prefer_async: bool = False,
    ) -> TenantOperationResult:
        """Apply a partial update to tenant settings."""

        headers: dict[str, str] | None = None
        if prefer_async:
            headers = {"Prefer": "respond-async"}
        body = self._prepare_payload(patch)
        resp = self.http.patch(
            "tenantsettings",
            params=self._params(),
            json=body,
            headers=headers,
        )
        resource: TenantSettings | None = None
        if resp.text:
            resource = TenantSettings.model_validate(resp.json())
        return TenantOperationResult(
            resource, resp.status_code, resp.headers.get("Operation-Location")
        )

    def request_settings_access(
        self,
        request: Mapping[str, Any] | TenantSettingsAccessRequest,
    ) -> None:
        """Submit an access request for tenant settings."""

        body = self._prepare_payload(request)
        self.http.post(
            "tenantsettings/requestAccess",
            params=self._params(),
            json=body,
        )

    def list_feature_controls(self) -> TenantFeatureControlList:
        """List tenant feature controls and current toggle states."""

        resp = self.http.get("tenantsettings/featureControl", params=self._params())
        return TenantFeatureControlList.model_validate(resp.json())

    def get_feature_control(self, feature_name: str) -> TenantFeatureControl:
        """Retrieve the control metadata for a specific feature."""

        resp = self.http.get(
            f"tenantsettings/featureControl/{feature_name}",
            params=self._params(),
        )
        return TenantFeatureControl.model_validate(resp.json())

    def update_feature_control(
        self,
        feature_name: str,
        patch: Mapping[str, Any] | TenantFeatureControlPatch,
        *,
        prefer_async: bool = False,
    ) -> TenantOperationResult:
        """Update the toggle state for a feature flight."""

        headers: dict[str, str] | None = None
        if prefer_async:
            headers = {"Prefer": "respond-async"}
        body = self._prepare_payload(patch)
        resp = self.http.patch(
            f"tenantsettings/featureControl/{feature_name}",
            params=self._params(),
            json=body,
            headers=headers,
        )
        resource: TenantFeatureControl | None = None
        if resp.text:
            resource = TenantFeatureControl.model_validate(resp.json())
        return TenantOperationResult(
            resource, resp.status_code, resp.headers.get("Operation-Location")
        )

    def request_feature_access(
        self,
        feature_name: str,
        request: Mapping[str, Any] | TenantFeatureAccessRequest,
    ) -> None:
        """Request access to update a feature control."""

        body = self._prepare_payload(request)
        self.http.post(
            f"tenantsettings/featureControl/{feature_name}/requestAccess",
            params=self._params(),
            json=body,
        )


__all__ = [
    "TenantOperationResult",
    "TenantSettingsClient",
]
