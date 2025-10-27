"""Client bindings for Authorization RBAC role definitions and assignments."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Any, cast

from pydantic import BaseModel

from ..http_client import HttpClient
from ..models.authorization import (
    CreateRoleAssignmentRequest,
    CreateRoleDefinitionRequest,
    RoleAssignment,
    RoleAssignmentListResult,
    RoleDefinition,
    RoleDefinitionListResult,
    UpdateRoleDefinitionRequest,
)

DEFAULT_API_VERSION = "2022-03-01-preview"


class AuthorizationRbacClient:
    """Typed wrapper for Power Platform Authorization RBAC endpoints."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        *,
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def _with_version(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            params.update(extra)
        return params

    @staticmethod
    def _dump(payload: Any) -> dict[str, Any]:
        if isinstance(payload, BaseModel):
            return payload.model_dump(by_alias=True, exclude_none=True)
        return cast(dict[str, Any], payload)

    def list_role_definitions(self) -> list[RoleDefinition]:
        """Return all role definitions available to the caller."""

        response = self.http.get(
            "authorization/rbac/roleDefinitions", params=self._with_version()
        )
        data = RoleDefinitionListResult.model_validate(response.json())
        return data.value

    def create_role_definition(
        self, request: CreateRoleDefinitionRequest | dict[str, Any]
    ) -> RoleDefinition:
        """Create a custom role definition."""

        payload = self._dump(request)
        response = self.http.post(
            "authorization/rbac/roleDefinitions",
            params=self._with_version(),
            json=payload,
        )
        return RoleDefinition.model_validate(response.json())

    def update_role_definition(
        self,
        role_definition_id: str,
        request: UpdateRoleDefinitionRequest | dict[str, Any],
    ) -> RoleDefinition:
        """Update fields on an existing custom role definition."""

        payload = self._dump(request)
        response = self.http.patch(
            f"authorization/rbac/roleDefinitions/{role_definition_id}",
            params=self._with_version(),
            json=payload,
        )
        return RoleDefinition.model_validate(response.json())

    def delete_role_definition(self, role_definition_id: str) -> None:
        """Delete a custom role definition."""

        self.http.delete(
            f"authorization/rbac/roleDefinitions/{role_definition_id}",
            params=self._with_version(),
        )

    def list_role_assignments(
        self, *, principal_id: str | None = None, scope: str | None = None
    ) -> list[RoleAssignment]:
        """Return role assignments filtered by principal or scope when provided."""

        params: dict[str, Any] = {}
        if principal_id:
            params["principalId"] = principal_id
        if scope:
            params["scope"] = scope
        response = self.http.get(
            "authorization/rbac/roleAssignments",
            params=self._with_version(params),
        )
        data = RoleAssignmentListResult.model_validate(response.json())
        return data.value

    def create_role_assignment(
        self, request: CreateRoleAssignmentRequest | dict[str, Any]
    ) -> RoleAssignment:
        """Assign a role definition to a principal for a given scope."""

        payload = self._dump(request)
        response = self.http.post(
            "authorization/rbac/roleAssignments",
            params=self._with_version(),
            json=payload,
        )
        return RoleAssignment.model_validate(response.json())

    def delete_role_assignment(self, assignment_id: str) -> None:
        """Remove a role assignment."""

        self.http.delete(
            f"authorization/rbac/roleAssignments/{assignment_id}",
            params=self._with_version(),
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> AuthorizationRbacClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = ["AuthorizationRbacClient"]

