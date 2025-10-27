"""Typed models for Policy Data Loss Prevention operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectorReference(BaseModel):
    """Reference to a connector captured within a DLP policy group."""

    id: str
    display_name: str | None = Field(default=None, alias="displayName")
    tier: str | None = None
    category: str | None = None
    is_custom: bool | None = Field(default=None, alias="isCustom")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ConnectorGroup(BaseModel):
    """Classification bucket applied to a set of connectors."""

    classification: str
    connectors: list[ConnectorReference]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class PolicyAssignment(BaseModel):
    """Assignment metadata linking a DLP policy to an environment."""

    assignment_id: str | None = Field(default=None, alias="assignmentId")
    environment_id: str = Field(alias="environmentId")
    environment_name: str | None = Field(default=None, alias="environmentName")
    assignment_type: str = Field(alias="assignmentType")
    region_group: str | None = Field(default=None, alias="regionGroup")
    applied_on: str | None = Field(default=None, alias="appliedOn")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class DataLossPreventionPolicy(BaseModel):
    """Tenant or environment scoped DLP policy definition."""

    id: str | None = None
    display_name: str = Field(alias="displayName")
    description: str | None = None
    created_time: str | None = Field(default=None, alias="createdTime")
    modified_time: str | None = Field(default=None, alias="modifiedTime")
    state: str
    policy_scope: str | None = Field(default=None, alias="policyScope")
    owner: dict[str, Any] | None = None
    connector_groups: list[ConnectorGroup] | None = Field(
        default=None, alias="connectorGroups"
    )
    assignments: list[PolicyAssignment] | None = None
    etag: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AsyncOperation(BaseModel):
    """Representation of a long running policy operation."""

    operation_id: str = Field(alias="operationId")
    status: str
    created_time: str | None = Field(default=None, alias="createdTime")
    last_updated_time: str | None = Field(default=None, alias="lastUpdatedTime")
    resource_location: str | None = Field(default=None, alias="resourceLocation")
    error: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "AsyncOperation",
    "ConnectorGroup",
    "ConnectorReference",
    "DataLossPreventionPolicy",
    "PolicyAssignment",
]
