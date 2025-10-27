"""Power Pages admin API client covering lifecycle, WAF, and security endpoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import httpx

from ..http_client import HttpClient

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class WebsiteOperationHandle:
    """Metadata emitted by asynchronous Power Pages admin operations."""

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def operation_id(self) -> str | None:
        """Return the trailing identifier from :attr:`operation_location`."""

        if not self.operation_location:
            return None
        return self.operation_location.rstrip("/").split("/")[-1]


class PowerPagesAdminClient:
    """Client wrapper for Power Pages admin endpoints."""

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
        """Close the underlying HTTP session."""

        self.http.close()

    def __enter__(self) -> PowerPagesAdminClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _with_api_version(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            params.update(extra)
        return params

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    def _post_operation(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> WebsiteOperationHandle:
        resp = self.http.post(path, params=params or self._with_api_version(), json=body)
        return WebsiteOperationHandle(
            resp.headers.get("Operation-Location"), self._parse_response(resp)
        )

    def _put_operation(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> WebsiteOperationHandle:
        resp = self.http.put(path, params=params or self._with_api_version(), json=body)
        return WebsiteOperationHandle(
            resp.headers.get("Operation-Location"), self._parse_response(resp)
        )

    def _patch_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        resp = self.http.patch(path, params=params or self._with_api_version(), json=body)
        return self._parse_response(resp)

    def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = self.http.get(path, params=params or self._with_api_version())
        return self._parse_response(resp)

    def start_website(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        """Start a Power Pages website."""

        return self._post_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/start"
        )

    def stop_website(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        """Stop a Power Pages website."""

        return self._post_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/stop"
        )

    def start_quick_scan(
        self,
        environment_id: str,
        website_id: str,
        *,
        lcid: int | None = None,
    ) -> WebsiteOperationHandle:
        """Trigger a quick security scan."""

        params = {"lcid": lcid} if lcid is not None else None
        return self._post_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/scan/quick/execute",
            params=self._with_api_version(params),
        )

    def start_deep_scan(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        """Trigger a deep security scan."""

        return self._post_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/scan/deep/start"
        )

    def get_security_score(self, environment_id: str, website_id: str) -> dict[str, Any]:
        """Return the current portal security score."""

        return self._get_json(
            f"powerpages/environments/{environment_id}/websites/{website_id}/scan/deep/getSecurityScore"
        )

    def get_security_report(self, environment_id: str, website_id: str) -> dict[str, Any]:
        """Return the most recent portal security scan report."""

        return self._get_json(
            f"powerpages/environments/{environment_id}/websites/{website_id}/scan/deep/getLatestCompletedReport"
        )

    def enable_waf(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        """Enable the Power Pages web application firewall."""

        return self._post_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/enableWaf"
        )

    def disable_waf(self, environment_id: str, website_id: str) -> WebsiteOperationHandle:
        """Disable the Power Pages web application firewall."""

        return self._post_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/disableWaf"
        )

    def get_waf_status(self, environment_id: str, website_id: str) -> dict[str, Any]:
        """Return the current web application firewall configuration."""

        return self._get_json(
            f"powerpages/environments/{environment_id}/websites/{website_id}/getWafStatus"
        )

    def create_waf_rules(
        self,
        environment_id: str,
        website_id: str,
        rules: dict[str, Any],
    ) -> WebsiteOperationHandle:
        """Replace the WAF ruleset for a website."""

        return self._put_operation(
            f"powerpages/environments/{environment_id}/websites/{website_id}/createWafRules",
            body=rules,
        )

    def get_waf_rules(
        self,
        environment_id: str,
        website_id: str,
        *,
        rule_type: str | None = None,
    ) -> dict[str, Any]:
        """Return the currently configured WAF rules."""

        params = {"ruleType": rule_type} if rule_type else None
        return self._get_json(
            f"powerpages/environments/{environment_id}/websites/{website_id}/getWafRules",
            params=self._with_api_version(params),
        )

    def update_site_visibility(
        self,
        environment_id: str,
        website_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Update anonymous or authenticated access visibility settings."""

        return self._patch_json(
            f"powerpages/environments/{environment_id}/websites/{website_id}/siteVisibility",
            body=payload,
        )

    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 900.0,
        on_update: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Poll an operation URL until the admin task completes."""

        from ..utils.poller import poll_until

        terminal_states = {"succeeded", "failed", "canceled", "cancelled", "completed"}

        def get_status() -> dict[str, Any]:
            resp = self.http.get(operation_url)
            return self._parse_response(resp)

        def is_done(status: dict[str, Any]) -> bool:
            state = str(status.get("status") or status.get("state") or "").lower()
            if state in terminal_states:
                return True
            return bool(status.get("endTime") or status.get("completedOn"))

        def get_progress(status: dict[str, Any]) -> int | None:
            for key in ("percentComplete", "progress", "percentage", "completionPercent"):
                value = status.get(key)
                if isinstance(value, int | float):
                    return int(value)
            return None

        return poll_until(
            get_status,
            is_done,
            get_progress,
            interval=interval,
            timeout=timeout,
            on_update=on_update,
        )


__all__ = ["PowerPagesAdminClient", "WebsiteOperationHandle", "DEFAULT_API_VERSION"]
