"""Typed models for Power Platform user management APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminRoleAssignment(BaseModel):
    """Details about an admin role assignment for a user."""

    id: str | None = None
    user_id: str | None = Field(default=None, alias="userId")
    role_definition_id: str | None = Field(default=None, alias="roleDefinitionId")
    role_display_name: str | None = Field(default=None, alias="roleDisplayName")
    scope: str | None = None
    assigned_by: str | None = Field(default=None, alias="assignedBy")
    assigned_datetime: str | None = Field(default=None, alias="assignedDateTime")
    removal_datetime: str | None = Field(default=None, alias="removalDateTime")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdminRoleAssignmentList(BaseModel):
    """Paged collection of admin role assignments."""

    value: list[AdminRoleAssignment] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")

    model_config = ConfigDict(populate_by_name=True)


class RemoveAdminRoleRequest(BaseModel):
    """Payload for removing an admin role from a user."""

    role_definition_id: str = Field(alias="roleDefinitionId")

    model_config = ConfigDict(populate_by_name=True)


class AsyncOperationStatus(BaseModel):
    """Status of a long-running user management operation."""

    id: str | None = None
    name: str | None = None
    status: str | None = None
    start_time: str | None = Field(default=None, alias="startTime")
    last_updated_time: str | None = Field(default=None, alias="lastUpdatedTime")
    percent_complete: float | None = Field(default=None, alias="percentComplete")
    target_resource_id: str | None = Field(default=None, alias="targetResourceId")
    target_resource_type: str | None = Field(default=None, alias="targetResourceType")
    error: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "AdminRoleAssignment",
    "AdminRoleAssignmentList",
    "RemoveAdminRoleRequest",
    "AsyncOperationStatus",
]
