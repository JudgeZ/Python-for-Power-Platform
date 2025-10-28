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


class AppSummary(BaseModel):
    """Summary metadata for a Power App returned by admin APIs."""

    id: str | None = None
    name: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    environment_id: str | None = Field(default=None, alias="environmentId")
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AppListPage(BaseModel):
    """Page of admin app results with continuation token support."""

    value: list[AppSummary] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")
    continuation_token: str | None = Field(default=None, alias="continuationToken")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AppVersionList(BaseModel):
    """Container for Power App versions with continuation metadata."""

    value: list[AppVersion] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")
    continuation_token: str | None = Field(default=None, alias="continuationToken")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SharePrincipal(BaseModel):
    """Representation of a principal used in share operations."""

    id: str
    principal_type: str = Field(alias="principalType")
    role_name: str = Field(alias="roleName")
    email: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class ShareAppRequest(BaseModel):
    """Payload for sharing an app with principals."""

    principals: list[SharePrincipal]
    notify_share_targets: bool | None = Field(default=None, alias="notifyShareTargets")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class RevokeShareRequest(BaseModel):
    """Payload for revoking app access from principals."""

    principal_ids: list[str] = Field(alias="principalIds")
    notify_share_targets: bool | None = Field(default=None, alias="notifyShareTargets")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class SetOwnerRequest(BaseModel):
    """Payload for assigning a new app owner."""

    owner: SharePrincipal
    keep_existing_owner_as_co_owner: bool | None = Field(
        default=None, alias="keepExistingOwnerAsCoOwner"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


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
