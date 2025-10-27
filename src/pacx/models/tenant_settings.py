"""Typed representations for Power Platform tenant settings operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TenantBooleanSetting(BaseModel):
    """Tenant-level toggle with state metadata."""

    value: bool | None = None
    requested_value: bool | None = Field(default=None, alias="requestedValue")
    effective_value: bool | None = Field(default=None, alias="effectiveValue")
    state: str | None = None
    last_updated_on: str | None = Field(default=None, alias="lastUpdatedOn")
    requested_on: str | None = Field(default=None, alias="requestedOn")
    requested_by: str | None = Field(default=None, alias="requestedBy")
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TenantBooleanSettingUpdate(BaseModel):
    value: bool | None = None
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantStringArraySetting(BaseModel):
    value: list[str] | None = None
    requested_value: list[str] | None = Field(default=None, alias="requestedValue")
    effective_value: list[str] | None = Field(default=None, alias="effectiveValue")
    state: str | None = None
    last_updated_on: str | None = Field(default=None, alias="lastUpdatedOn")
    requested_on: str | None = Field(default=None, alias="requestedOn")
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TenantStringArraySettingUpdate(BaseModel):
    value: list[str] | None = None
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantThrottlingLimits(BaseModel):
    limit: int | None = None
    interval_in_minutes: int | None = Field(default=None, alias="intervalInMinutes")
    scope: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantThrottlingSetting(BaseModel):
    value: TenantThrottlingLimits | None = None
    requested_value: TenantThrottlingLimits | None = Field(default=None, alias="requestedValue")
    effective_value: TenantThrottlingLimits | None = Field(default=None, alias="effectiveValue")
    state: str | None = None
    last_updated_on: str | None = Field(default=None, alias="lastUpdatedOn")
    requested_on: str | None = Field(default=None, alias="requestedOn")
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TenantThrottlingSettingUpdate(BaseModel):
    value: TenantThrottlingLimits | None = None
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantMakerOnboardingSetting(BaseModel):
    value: str | None = None
    allowed_values: list[str] | None = Field(default=None, alias="allowedValues")
    requested_value: str | None = Field(default=None, alias="requestedValue")
    state: str | None = None
    last_updated_on: str | None = Field(default=None, alias="lastUpdatedOn")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TenantMakerOnboardingSettingUpdate(BaseModel):
    value: str | None = None
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantSettings(BaseModel):
    disable_community_sharing: TenantBooleanSetting | None = Field(
        default=None, alias="disableCommunitySharing"
    )
    disable_discoverability: TenantBooleanSetting | None = Field(
        default=None, alias="disableDiscoverability"
    )
    disable_newsletter_signup: TenantBooleanSetting | None = Field(
        default=None, alias="disableNewsletterSignup"
    )
    disable_support_tickets: TenantBooleanSetting | None = Field(
        default=None, alias="disableSupportTickets"
    )
    disable_trial_environment_creation: TenantBooleanSetting | None = Field(
        default=None, alias="disableTrialEnvironmentCreation"
    )
    disable_production_environment_creation: TenantBooleanSetting | None = Field(
        default=None, alias="disableProductionEnvironmentCreation"
    )
    disable_portal_custom_domains: TenantBooleanSetting | None = Field(
        default=None, alias="disablePortalCustomDomains"
    )
    disable_power_apps_evaluation_environment_creation: TenantBooleanSetting | None = Field(
        default=None, alias="disablePowerAppsEvaluationEnvironmentCreation"
    )
    allowed_environment_types: TenantStringArraySetting | None = Field(
        default=None, alias="allowedEnvironmentTypes"
    )
    allowed_billing_policies: TenantStringArraySetting | None = Field(
        default=None, alias="allowedBillingPolicies"
    )
    power_automate_requests: TenantThrottlingSetting | None = Field(
        default=None, alias="powerAutomateRequests"
    )
    app_insights_instrumentation_keys: TenantStringArraySetting | None = Field(
        default=None, alias="appInsightsInstrumentationKeys"
    )
    api_throttling_policy: TenantThrottlingSetting | None = Field(
        default=None, alias="apiThrottlingPolicy"
    )
    power_pages_maker_access: TenantBooleanSetting | None = Field(
        default=None, alias="powerPagesMakerAccess"
    )
    managed_environment: TenantBooleanSetting | None = Field(
        default=None, alias="managedEnvironment"
    )
    analytics_sharing: TenantBooleanSetting | None = Field(default=None, alias="analyticsSharing")
    experimental_features: TenantStringArraySetting | None = Field(
        default=None, alias="experimentalFeatures"
    )
    maker_onboarding: TenantMakerOnboardingSetting | None = Field(
        default=None, alias="makerOnboarding"
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantSettingsPatch(BaseModel):
    disable_community_sharing: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disableCommunitySharing"
    )
    disable_discoverability: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disableDiscoverability"
    )
    disable_newsletter_signup: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disableNewsletterSignup"
    )
    disable_support_tickets: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disableSupportTickets"
    )
    disable_trial_environment_creation: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disableTrialEnvironmentCreation"
    )
    disable_production_environment_creation: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disableProductionEnvironmentCreation"
    )
    disable_portal_custom_domains: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disablePortalCustomDomains"
    )
    disable_power_apps_evaluation_environment_creation: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="disablePowerAppsEvaluationEnvironmentCreation"
    )
    allowed_environment_types: TenantStringArraySettingUpdate | None = Field(
        default=None, alias="allowedEnvironmentTypes"
    )
    allowed_billing_policies: TenantStringArraySettingUpdate | None = Field(
        default=None, alias="allowedBillingPolicies"
    )
    power_automate_requests: TenantThrottlingSettingUpdate | None = Field(
        default=None, alias="powerAutomateRequests"
    )
    app_insights_instrumentation_keys: TenantStringArraySettingUpdate | None = Field(
        default=None, alias="appInsightsInstrumentationKeys"
    )
    api_throttling_policy: TenantThrottlingSettingUpdate | None = Field(
        default=None, alias="apiThrottlingPolicy"
    )
    power_pages_maker_access: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="powerPagesMakerAccess"
    )
    managed_environment: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="managedEnvironment"
    )
    analytics_sharing: TenantBooleanSettingUpdate | None = Field(
        default=None, alias="analyticsSharing"
    )
    experimental_features: TenantStringArraySettingUpdate | None = Field(
        default=None, alias="experimentalFeatures"
    )
    maker_onboarding: TenantMakerOnboardingSettingUpdate | None = Field(
        default=None, alias="makerOnboarding"
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantSettingsAccessRequest(BaseModel):
    justification: str
    requested_settings: list[str] | None = Field(default=None, alias="requestedSettings")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantFeatureControl(BaseModel):
    name: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    description: str | None = None
    state: str | None = None
    value: bool | None = None
    requested_value: bool | None = Field(default=None, alias="requestedValue")
    effective_value: bool | None = Field(default=None, alias="effectiveValue")
    last_updated_on: str | None = Field(default=None, alias="lastUpdatedOn")
    requested_on: str | None = Field(default=None, alias="requestedOn")
    justification: str | None = None
    environments: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TenantFeatureControlPatch(BaseModel):
    value: bool | None = None
    justification: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantFeatureControlList(BaseModel):
    value: list[TenantFeatureControl] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class TenantFeatureAccessRequest(BaseModel):
    justification: str

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


__all__ = [
    "TenantBooleanSetting",
    "TenantBooleanSettingUpdate",
    "TenantFeatureAccessRequest",
    "TenantFeatureControl",
    "TenantFeatureControlList",
    "TenantFeatureControlPatch",
    "TenantMakerOnboardingSetting",
    "TenantMakerOnboardingSettingUpdate",
    "TenantSettings",
    "TenantSettingsAccessRequest",
    "TenantSettingsPatch",
    "TenantStringArraySetting",
    "TenantStringArraySettingUpdate",
    "TenantThrottlingLimits",
    "TenantThrottlingSetting",
    "TenantThrottlingSettingUpdate",
]
