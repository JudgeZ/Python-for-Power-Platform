from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import httpx

from ..http_client import HttpClient
from ..models.pva import (
    BotListResult,
    BotMetadata,
    ChannelConfiguration,
    ChannelConfigurationListResult,
    ChannelConfigurationPayload,
    ExportBotPackageRequest,
    ImportBotPackageRequest,
    PublishBotRequest,
    UnpublishBotRequest,
)
from ..utils.poller import poll_until

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class OperationHandle:
    """Metadata returned by long-running Power Virtual Agents operations."""

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def operation_id(self) -> str | None:
        if not self.operation_location:
            return None
        return self.operation_location.rstrip("/").split("/")[-1]


class PVAClient:
    """Client for the Power Virtual Agents bots API surface."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        *,
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> PVAClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _with_api_version(self, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            for key, value in extra.items():
                if value is not None:
                    params[key] = value
        return params

    @staticmethod
    def _parse_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    @staticmethod
    def _dump_payload(payload: Any) -> dict[str, Any]:
        if payload is None:
            return {}
        if hasattr(payload, "model_dump"):
            return cast(dict[str, Any], payload.model_dump(by_alias=True, exclude_none=True))
        if isinstance(payload, Mapping):
            return {k: v for k, v in payload.items() if v is not None}
        raise TypeError(f"Unsupported payload type: {type(payload)!r}")

    def _post_operation(
        self,
        path: str,
        *,
        body: Any | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> OperationHandle:
        json_body: dict[str, Any] | None = None
        if body is not None:
            json_body = self._dump_payload(body)
            if not json_body:
                json_body = None
        resp = self.http.post(path, params=params or self._with_api_version(), json=json_body)
        payload = self._parse_dict(resp)
        return OperationHandle(resp.headers.get("Operation-Location"), payload)

    def list_bots(self, environment_id: str, *, top: int | None = None) -> list[BotMetadata]:
        """List bots available within an environment."""

        params = self._with_api_version({"top": str(top) if top is not None else None})
        resp = self.http.get(
            f"powervirtualagents/environments/{environment_id}/bots",
            params=params,
        )
        data = BotListResult.model_validate(resp.json())
        return data.value

    def get_bot(self, environment_id: str, bot_id: str) -> BotMetadata:
        """Retrieve metadata for a single bot."""

        resp = self.http.get(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}",
            params=self._with_api_version(),
        )
        return BotMetadata.model_validate(resp.json())

    def publish_bot(
        self,
        environment_id: str,
        bot_id: str,
        request: PublishBotRequest | Mapping[str, Any] | None,
    ) -> OperationHandle:
        """Publish the specified bot."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/publish",
            body=request,
        )

    def unpublish_bot(
        self,
        environment_id: str,
        bot_id: str,
        request: UnpublishBotRequest | Mapping[str, Any] | None = None,
    ) -> OperationHandle:
        """Unpublish the specified bot."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/unpublish",
            body=request,
        )

    def export_bot_package(
        self,
        environment_id: str,
        bot_id: str,
        request: ExportBotPackageRequest | Mapping[str, Any],
    ) -> OperationHandle:
        """Export a bot package."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/export",
            body=request,
        )

    def import_bot_package(
        self,
        environment_id: str,
        bot_id: str,
        request: ImportBotPackageRequest | Mapping[str, Any],
    ) -> OperationHandle:
        """Import a bot package."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/import",
            body=request,
        )

    def list_channels(self, environment_id: str, bot_id: str) -> list[ChannelConfiguration]:
        """List channel configurations for a bot."""

        resp = self.http.get(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/channels",
            params=self._with_api_version(),
        )
        data = ChannelConfigurationListResult.model_validate(resp.json())
        return data.value

    def get_channel(
        self, environment_id: str, bot_id: str, channel_id: str
    ) -> ChannelConfiguration:
        """Fetch a specific channel configuration."""

        resp = self.http.get(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/channels/{channel_id}",
            params=self._with_api_version(),
        )
        return ChannelConfiguration.model_validate(resp.json())

    def create_channel(
        self,
        environment_id: str,
        bot_id: str,
        payload: ChannelConfigurationPayload | Mapping[str, Any],
    ) -> OperationHandle:
        """Enable a channel configuration for the bot."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/channels",
            body=payload,
        )

    def update_channel(
        self,
        environment_id: str,
        bot_id: str,
        channel_id: str,
        payload: ChannelConfigurationPayload | Mapping[str, Any],
    ) -> OperationHandle:
        """Update an existing channel configuration."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/channels/{channel_id}",
            body=payload,
        )

    def delete_channel(self, environment_id: str, bot_id: str, channel_id: str) -> OperationHandle:
        """Disable a channel configuration."""

        resp = self.http.delete(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/channels/{channel_id}",
            params=self._with_api_version(),
        )
        payload = self._parse_dict(resp)
        return OperationHandle(resp.headers.get("Operation-Location"), payload)

    def get_quarantine_status(self, environment_id: str, bot_id: str) -> dict[str, Any]:
        """Retrieve the quarantine status for a bot."""

        resp = self.http.get(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/quarantine/status",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def set_quarantined(self, environment_id: str, bot_id: str) -> OperationHandle:
        """Set a bot to quarantined state."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/quarantine/set",
        )

    def set_unquarantined(self, environment_id: str, bot_id: str) -> OperationHandle:
        """Remove quarantine from a bot."""

        return self._post_operation(
            f"powervirtualagents/environments/{environment_id}/bots/{bot_id}/quarantine/unset",
        )

    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        """Poll an operation URL until a terminal state is reached."""

        done_states = {"succeeded", "failed", "canceled", "cancelled"}

        def get_status() -> dict[str, Any]:
            resp = self.http.get(operation_url)
            return self._parse_dict(resp)

        def is_done(status: dict[str, Any]) -> bool:
            state = str(status.get("status", "")).lower()
            return state in done_states

        return poll_until(get_status, is_done, interval=interval, timeout=timeout)


__all__ = ["DEFAULT_API_VERSION", "OperationHandle", "PVAClient"]
