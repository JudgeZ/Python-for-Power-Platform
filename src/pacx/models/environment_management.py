from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .power_platform import EnvironmentSummary


class EnvironmentListPage(BaseModel):
    """Page of environment summaries returned by the admin APIs."""

    value: list[EnvironmentSummary] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")
    continuation_token: str | None = Field(default=None, alias="continuationToken")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnvironmentLifecycleOperation(BaseModel):
    """Metadata describing a long-running environment management operation."""

    operation_id: str | None = Field(default=None, alias="operationId")
    status: str | None = None
    resource_location: str | None = Field(default=None, alias="resourceLocation")
    created_date_time: str | None = Field(default=None, alias="createdDateTime")
    last_updated_date_time: str | None = Field(default=None, alias="lastUpdatedDateTime")
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnvironmentCreateRequest(BaseModel):
    """Payload for provisioning a new Power Platform environment."""

    display_name: str = Field(alias="displayName")
    region: str
    environment_sku: str = Field(alias="environmentSku")
    description: str | None = None
    environment_type: str | None = Field(default=None, alias="environmentType")
    domain_name: str | None = Field(default=None, alias="domainName")
    security_group_id: str | None = Field(default=None, alias="securityGroupId")
    tenant_id: str | None = Field(default=None, alias="tenantId")
    azure_subscription_id: str | None = Field(default=None, alias="azureSubscriptionId")
    billing_policy_id: str | None = Field(default=None, alias="billingPolicyId")
    data_lake_storage_account_location: str | None = Field(
        default=None, alias="dataLakeStorageAccountLocation"
    )
    data_lake_storage_account_name: str | None = Field(
        default=None, alias="dataLakeStorageAccountName"
    )
    additional_settings: dict[str, Any] = Field(default_factory=dict, alias="additionalSettings")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnvironmentCopyRequest(BaseModel):
    """Request payload for copying an environment into a new target."""

    target_environment_name: str = Field(alias="targetEnvironmentName")
    target_environment_region: str = Field(alias="targetEnvironmentRegion")
    target_environment_sku: str | None = Field(default=None, alias="targetEnvironmentSku")
    copy_type: str | None = Field(default=None, alias="copyType")
    include_audit_data: bool | None = Field(default=None, alias="includeAuditData")
    include_flow_history: bool | None = Field(default=None, alias="includeFlowHistory")
    override_existing_environment: bool | None = Field(
        default=None, alias="overrideExistingEnvironment"
    )
    security_group_id: str | None = Field(default=None, alias="securityGroupId")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnvironmentBackupRequest(BaseModel):
    """Request payload for scheduling an environment backup."""

    label: str
    description: str | None = None
    is_manual: bool | None = Field(default=None, alias="isManual")
    retention_days: int | None = Field(default=None, alias="retentionDays")
    time_zone: str | None = Field(default=None, alias="timeZone")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnvironmentResetRequest(BaseModel):
    """Request payload for resetting an environment."""

    reset_type: str = Field(alias="resetType")
    target_environment_id: str | None = Field(default=None, alias="targetEnvironmentId")
    backup_id: str | None = Field(default=None, alias="backupId")
    notes: str | None = None
    skip_email_notification: bool | None = Field(default=None, alias="skipEmailNotification")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnvironmentRestoreRequest(BaseModel):
    """Request payload for restoring an environment from backup."""

    backup_id: str = Field(alias="backupId")
    target_environment_id: str | None = Field(default=None, alias="targetEnvironmentId")
    target_environment_region: str | None = Field(default=None, alias="targetEnvironmentRegion")
    restore_reason: str | None = Field(default=None, alias="restoreReason")
    notes: str | None = None
    skip_audit_data: bool | None = Field(default=None, alias="skipAuditData")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "EnvironmentBackupRequest",
    "EnvironmentCopyRequest",
    "EnvironmentCreateRequest",
    "EnvironmentLifecycleOperation",
    "EnvironmentListPage",
    "EnvironmentResetRequest",
    "EnvironmentRestoreRequest",
]
