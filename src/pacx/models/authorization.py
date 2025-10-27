"""Pydantic models for Authorization (RBAC) role definitions and assignments."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RolePermission(BaseModel):
    """Permissions granted or denied by a role definition."""

    actions: list[str] = Field(default_factory=list)
    not_actions: list[str] = Field(default_factory=list, alias="notActions")
    data_actions: list[str] = Field(default_factory=list, alias="dataActions")
    not_data_actions: list[str] = Field(default_factory=list, alias="notDataActions")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class RoleDefinition(BaseModel):
    """Role definition metadata returned by the Authorization RBAC APIs."""

    id: str
    name: str
    description: str | None = None
    is_built_in: bool | None = Field(default=None, alias="isBuiltIn")
    permissions: list[RolePermission] = Field(default_factory=list)
    assignable_scopes: list[str] = Field(default_factory=list, alias="assignableScopes")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class RoleDefinitionListResult(BaseModel):
    """Container for paged role definition results."""

    value: list[RoleDefinition] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")

    model_config = ConfigDict(populate_by_name=True)


class CreateRoleDefinitionRequest(BaseModel):
    """Payload used to create a custom role definition."""

    name: str
    description: str | None = None
    permissions: list[RolePermission]
    assignable_scopes: list[str] = Field(alias="assignableScopes")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class UpdateRoleDefinitionRequest(BaseModel):
    """Payload used to update an existing custom role definition."""

    name: str | None = None
    description: str | None = None
    permissions: list[RolePermission] | None = None
    assignable_scopes: list[str] | None = Field(default=None, alias="assignableScopes")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class RoleAssignment(BaseModel):
    """Role assignment metadata linking principals, scopes, and definitions."""

    id: str
    principal_id: str = Field(alias="principalId")
    role_definition_id: str = Field(alias="roleDefinitionId")
    scope: str
    created_on: str | None = Field(default=None, alias="createdOn")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class RoleAssignmentListResult(BaseModel):
    """Container for paged role assignment results."""

    value: list[RoleAssignment] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")

    model_config = ConfigDict(populate_by_name=True)


class CreateRoleAssignmentRequest(BaseModel):
    """Payload used to grant a role to a principal at a given scope."""

    principal_id: str = Field(alias="principalId")
    role_definition_id: str = Field(alias="roleDefinitionId")
    scope: str

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


__all__ = [
    "RolePermission",
    "RoleDefinition",
    "RoleDefinitionListResult",
    "CreateRoleDefinitionRequest",
    "UpdateRoleDefinitionRequest",
    "RoleAssignment",
    "RoleAssignmentListResult",
    "CreateRoleAssignmentRequest",
]

