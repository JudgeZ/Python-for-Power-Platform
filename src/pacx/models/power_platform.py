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
    properties: dict[str, Any] = Field(default_factory=dict)

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


class FlowTrigger(BaseModel):
    """Trigger metadata returned by the Power Automate APIs."""

    name: str | None = None
    type: str | None = None
    kind: str | None = None
    description: str | None = None
    recurrence: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FlowAction(BaseModel):
    """Action metadata returned by the flow actions endpoint."""

    name: str | None = None
    type: str | None = None
    description: str | None = None
    connector: str | None = None
    operation_id: str | None = Field(default=None, alias="operationId")
    inputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FlowActionList(BaseModel):
    """Container for flow actions and triggers discovered in an environment."""

    actions: list[FlowAction] = Field(default_factory=list)
    triggers: list[FlowTrigger] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FlowRunDiagnosticsIssue(BaseModel):
    """Individual diagnostic issue reported for a flow run."""

    action_name: str | None = Field(default=None, alias="actionName")
    code: str | None = None
    message: str | None = None
    recommendation: str | None = None
    timestamp: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FlowRunDiagnostics(BaseModel):
    """Diagnostics payload for a specific flow run."""

    run_name: str | None = Field(default=None, alias="runName")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    issues: list[FlowRunDiagnosticsIssue] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")
