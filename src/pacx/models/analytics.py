from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdvisorScenario(BaseModel):
    """Advisor recommendation scenario metadata."""

    scenario: str | None = None
    scenario_name: str | None = Field(default=None, alias="scenarioName")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorAction(BaseModel):
    """Executable action metadata for a scenario."""

    action_name: str | None = Field(default=None, alias="actionName")
    display_name: str | None = Field(default=None, alias="displayName")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorRecommendationResource(BaseModel):
    """Resource impacted by an advisor recommendation."""

    resource_id: str | None = Field(default=None, alias="resourceId")
    resource_name: str | None = Field(default=None, alias="resourceName")
    resource_type: str | None = Field(default=None, alias="resourceType")
    environment_id: str | None = Field(default=None, alias="environmentId")
    additional_properties: dict[str, Any] = Field(default_factory=dict, alias="properties")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorRecommendationDetail(BaseModel):
    """Detailed recommendation payload returned by analytics endpoints."""

    recommendation_id: str = Field(alias="recommendationId")
    scenario: str
    title: str
    summary: str | None = None
    category: str | None = None
    severity: str
    impact: str | None = None
    detected_date_time: str | None = Field(default=None, alias="detectedDateTime")
    status: str | None = None
    remediation_steps: list[str] = Field(default_factory=list, alias="remediationSteps")
    impacted_resources: list[AdvisorRecommendationResource] = Field(
        default_factory=list, alias="impactedResources"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorRecommendationAcknowledgement(BaseModel):
    """Acknowledgement metadata returned by acknowledge/dismiss operations."""

    recommendation_id: str = Field(alias="recommendationId")
    scenario: str
    operation_id: str = Field(alias="operationId")
    status: str
    acknowledged_at: str | None = Field(default=None, alias="acknowledgedAt")
    acknowledged_by: str | None = Field(default=None, alias="acknowledgedBy")
    message: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorRecommendationActionResultSummary(BaseModel):
    """Summary for asynchronous recommendation operations."""

    outcome: str | None = None
    completed_at: str | None = Field(default=None, alias="completedAt")
    message: str | None = None
    errors: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorRecommendationOperationStatus(BaseModel):
    """Status metadata for an asynchronous recommendation operation."""

    operation_id: str = Field(alias="operationId")
    status: str
    started_at: str | None = Field(default=None, alias="startedAt")
    last_updated_at: str | None = Field(default=None, alias="lastUpdatedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    result_summary: AdvisorRecommendationActionResultSummary = Field(
        alias="resultSummary"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorRecommendationStatus(BaseModel):
    """Current lifecycle status for an advisor recommendation."""

    recommendation_id: str = Field(alias="recommendationId")
    scenario: str
    status: str
    last_updated: str | None = Field(default=None, alias="lastUpdated")
    acknowledged: bool | None = None
    dismissed: bool | None = None
    pending_operations: list[str] | None = Field(default=None, alias="pendingOperations")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorActionResult(BaseModel):
    """Per-resource outcome from executing an advisor action."""

    action_final_result: str | None = Field(default=None, alias="actionFinalResult")
    error: str | None = None
    error_code: str | None = Field(default=None, alias="errorCode")
    resource_id: str | None = Field(default=None, alias="resourceId")
    status_code: int | None = Field(default=None, alias="statusCode")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorActionResponse(BaseModel):
    """Response payload returned from executing an advisor action."""

    results: list[AdvisorActionResult] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdvisorActionRequest(BaseModel):
    """Payload submitted when executing an advisor action."""

    scenario: str
    action_parameters: dict[str, Any] = Field(default_factory=dict, alias="actionParameters")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class RecommendationActionPayload(BaseModel):
    """Optional payload for acknowledge and dismiss operations."""

    notes: str | None = None
    requested_by: str | None = Field(default=None, alias="requestedBy")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


__all__ = [
    "AdvisorAction",
    "AdvisorActionRequest",
    "AdvisorActionResponse",
    "AdvisorActionResult",
    "AdvisorRecommendationAcknowledgement",
    "AdvisorRecommendationActionResultSummary",
    "AdvisorRecommendationDetail",
    "AdvisorRecommendationOperationStatus",
    "AdvisorRecommendationResource",
    "AdvisorRecommendationStatus",
    "AdvisorScenario",
    "RecommendationActionPayload",
]
