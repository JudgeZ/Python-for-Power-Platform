from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentSummary(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = Field(default=None, alias="environmentType")
    location: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class PowerApp(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class CloudFlow(BaseModel):
    id: str | None = None
    name: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class FlowRun(BaseModel):
    id: str | None = None
    name: str | None = None
    status: str | None = None
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")

    model_config = ConfigDict(populate_by_name=True)


class AppVersion(BaseModel):
    """Metadata describing a published Power App version."""

    id: str | None = None
    name: str | None = None
    version_id: str | None = Field(default=None, alias="versionId")
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AppPermissionAssignment(BaseModel):
    """Representation of a permission granted to a Power App principal."""

    id: str | None = None
    role_name: str | None = Field(default=None, alias="roleName")
    principal_type: str | None = Field(default=None, alias="principalType")
    email: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")
