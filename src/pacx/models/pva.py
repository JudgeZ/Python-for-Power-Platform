from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BotMetadata(BaseModel):
    """Metadata describing a Power Virtual Agents bot."""

    id: str
    name: str
    environment_id: str = Field(alias="environmentId")
    display_name: str | None = Field(default=None, alias="displayName")
    description: str | None = None
    locale: str | None = None
    last_published_time: str | None = Field(default=None, alias="lastPublishedTime")
    created_time: str | None = Field(default=None, alias="createdTime")
    modified_time: str | None = Field(default=None, alias="modifiedTime")
    status: str | None = None
    author: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BotListResult(BaseModel):
    """Container for paginated bot listings."""

    value: list[BotMetadata] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")

    model_config = ConfigDict(populate_by_name=True)


class PublishBotRequest(BaseModel):
    """Payload used when publishing a bot."""

    comment: str | None = None
    locale: str | None = None
    target_environment_id: str | None = Field(default=None, alias="targetEnvironmentId")
    included_channels: list[str] | None = Field(default=None, alias="includedChannels")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class UnpublishBotRequest(BaseModel):
    """Payload used when unpublishing a bot."""

    comment: str | None = None
    channels: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class ExportBotPackageRequest(BaseModel):
    """Payload describing a bot export request."""

    package_format: str = Field(alias="packageFormat")
    include_analytics: bool | None = Field(default=None, alias="includeAnalytics")
    include_secrets: bool | None = Field(default=None, alias="includeSecrets")
    storage_url: str | None = Field(default=None, alias="storageUrl")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ImportBotPackageRequest(BaseModel):
    """Payload describing a bot import request."""

    package_url: str = Field(alias="packageUrl")
    overwrite_existing_resources: bool | None = Field(
        default=None, alias="overwriteExistingResources"
    )
    publish_on_completion: bool | None = Field(default=None, alias="publishOnCompletion")
    locale_mappings: dict[str, str] | None = Field(default=None, alias="localeMappings")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ChannelConfiguration(BaseModel):
    """Representation of a bot channel configuration."""

    id: str
    channel_type: str = Field(alias="channelType")
    status: str | None = None
    last_modified_time: str | None = Field(default=None, alias="lastModifiedTime")
    configuration: dict[str, Any] = Field(default_factory=dict)
    provisioning_state: str | None = Field(default=None, alias="provisioningState")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ChannelConfigurationPayload(BaseModel):
    """Payload used when enabling or updating a channel configuration."""

    channel_type: str = Field(alias="channelType")
    configuration: dict[str, Any] | None = None
    is_enabled: bool | None = Field(default=None, alias="isEnabled")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ChannelConfigurationListResult(BaseModel):
    """Container for paginated channel configuration results."""

    value: list[ChannelConfiguration] = Field(default_factory=list)
    next_link: str | None = Field(default=None, alias="nextLink")

    model_config = ConfigDict(populate_by_name=True)


__all__ = [
    "BotListResult",
    "BotMetadata",
    "ChannelConfiguration",
    "ChannelConfigurationListResult",
    "ChannelConfigurationPayload",
    "ExportBotPackageRequest",
    "ImportBotPackageRequest",
    "PublishBotRequest",
    "UnpublishBotRequest",
]
