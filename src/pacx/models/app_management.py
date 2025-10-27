from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationPackage(BaseModel):
    """Detailed metadata describing an application package installation."""

    id: str | None = None
    package_id: str | None = Field(default=None, alias="packageId")
    unique_name: str | None = Field(default=None, alias="uniqueName")
    display_name: str | None = Field(default=None, alias="displayName")
    publisher: str | None = None
    version: str | None = None
    environment_id: str | None = Field(default=None, alias="environmentId")
    application_type: str | None = Field(default=None, alias="applicationType")
    availability_state: str | None = Field(default=None, alias="availabilityState")
    is_managed: bool | None = Field(default=None, alias="isManaged")
    install_state: str | None = Field(default=None, alias="installState")
    created_time: str | None = Field(default=None, alias="createdTime")
    last_updated_time: str | None = Field(default=None, alias="lastUpdatedTime")
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ApplicationPackageSummary(BaseModel):
    """Summary view returned by the list application package APIs."""

    package_id: str | None = Field(default=None, alias="packageId")
    unique_name: str | None = Field(default=None, alias="uniqueName")
    display_name: str | None = Field(default=None, alias="displayName")
    environment_id: str | None = Field(default=None, alias="environmentId")
    application_type: str | None = Field(default=None, alias="applicationType")
    version: str | None = None
    availability_state: str | None = Field(default=None, alias="availabilityState")
    install_state: str | None = Field(default=None, alias="installState")
    managed: bool | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ApplicationPackageOperation(BaseModel):
    """Status payload describing a long-running application package operation."""

    operation_id: str | None = Field(default=None, alias="operationId")
    status: str | None = None
    operation_type: str | None = Field(default=None, alias="operationType")
    created_time: str | None = Field(default=None, alias="createdTime")
    last_updated_time: str | None = Field(default=None, alias="lastUpdatedTime")
    percent_complete: float | None = Field(default=None, alias="percentComplete")
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "ApplicationPackage",
    "ApplicationPackageSummary",
    "ApplicationPackageOperation",
]
