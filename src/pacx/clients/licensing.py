from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

import httpx

from ..http_client import HttpClient

DEFAULT_API_VERSION = "2022-03-01-preview"


@dataclass(frozen=True)
class LicensingOperation:
    """Container describing an asynchronous licensing operation."""

    operation_location: str | None
    metadata: dict[str, Any]

    @property
    def operation_id(self) -> str | None:
        """Return the trailing identifier from :attr:`operation_location`."""

        if not self.operation_location:
            return None
        return self.operation_location.rstrip("/").split("/")[-1]


class LicensingClient:
    """Client for Power Platform licensing and capacity APIs."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> LicensingClient:
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
    def _parse_dict(resp: httpx.Response) -> dict[str, Any]:
        if not resp.text:
            return {}
        try:
            data = resp.json()
        except Exception:  # pragma: no cover - defensive
            return {}
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    @staticmethod
    def _parse_list(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [cast(dict[str, Any], item) for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            value = data.get("value")
            if isinstance(value, list):
                return [cast(dict[str, Any], item) for item in value if isinstance(item, dict)]
        return []

    def _post_operation(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> LicensingOperation:
        resp = self.http.post(path, params=params or self._with_api_version(), json=body)
        payload = self._parse_dict(resp)
        return LicensingOperation(resp.headers.get("Operation-Location"), payload)

    # Billing policy operations -------------------------------------------------
    def create_billing_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.post(
            "licensing/billingPolicies", params=self._with_api_version(), json=payload
        )
        return self._parse_dict(resp)

    def list_billing_policies(self) -> list[dict[str, Any]]:
        resp = self.http.get("licensing/billingPolicies", params=self._with_api_version())
        return self._parse_list(self._parse_dict(resp))

    def get_billing_policy(self, policy_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/billingPolicies/{policy_id}",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def update_billing_policy(self, policy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.patch(
            f"licensing/billingPolicies/{policy_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_dict(resp)

    def delete_billing_policy(self, policy_id: str) -> None:
        self.http.delete(
            f"licensing/billingPolicies/{policy_id}", params=self._with_api_version()
        )

    def refresh_billing_policy_provisioning(self, policy_id: str) -> LicensingOperation:
        return self._post_operation(f"licensing/billingPolicies/{policy_id}:refreshProvisioningStatus")

    # Billing policy environment operations ------------------------------------
    def list_billing_policy_environments(self, policy_id: str) -> list[dict[str, Any]]:
        resp = self.http.get(
            f"licensing/billingPolicies/{policy_id}/environments",
            params=self._with_api_version(),
        )
        return self._parse_list(self._parse_dict(resp))

    def get_billing_policy_environment(self, policy_id: str, environment_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/billingPolicies/{policy_id}/environments/{environment_id}",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def add_billing_policy_environment(self, policy_id: str, environment_id: str) -> None:
        self.http.post(
            f"licensing/billingPolicies/{policy_id}/environments/{environment_id}",
            params=self._with_api_version(),
        )

    def remove_billing_policy_environment(self, policy_id: str, environment_id: str) -> None:
        self.http.delete(
            f"licensing/billingPolicies/{policy_id}/environments/{environment_id}",
            params=self._with_api_version(),
        )

    def get_environment_billing_policy(self, environment_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/environments/{environment_id}/billingPolicies/default",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    # Currency allocation & reports --------------------------------------------
    def get_currency_allocation(self, environment_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/environments/{environment_id}/currencyAllocation",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def patch_currency_allocation(
        self, environment_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        resp = self.http.patch(
            f"licensing/environments/{environment_id}/currencyAllocation",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_dict(resp)

    def list_currency_reports(self) -> list[dict[str, Any]]:
        resp = self.http.get("licensing/currencyReports", params=self._with_api_version())
        data = self._parse_dict(resp)
        return self._parse_list(data) or ([data] if data else [])

    # ISV contracts -------------------------------------------------------------
    def create_isv_contract(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.post("licensing/isvContracts", params=self._with_api_version(), json=payload)
        return self._parse_dict(resp)

    def list_isv_contracts(self) -> list[dict[str, Any]]:
        resp = self.http.get("licensing/isvContracts", params=self._with_api_version())
        return self._parse_list(self._parse_dict(resp))

    def get_isv_contract(self, contract_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/isvContracts/{contract_id}", params=self._with_api_version()
        )
        return self._parse_dict(resp)

    def update_isv_contract(self, contract_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.http.patch(
            f"licensing/isvContracts/{contract_id}",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_dict(resp)

    def delete_isv_contract(self, contract_id: str) -> None:
        self.http.delete(
            f"licensing/isvContracts/{contract_id}", params=self._with_api_version()
        )

    # Storage warnings ----------------------------------------------------------
    def list_storage_warnings(self) -> list[dict[str, Any]]:
        resp = self.http.get("licensing/storageWarnings", params=self._with_api_version())
        return self._parse_list(self._parse_dict(resp))

    def get_storage_warning(self, category: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/storageWarnings/{category}", params=self._with_api_version()
        )
        return self._parse_dict(resp)

    def get_storage_warning_entity(self, category: str, entity: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/storageWarnings/{category}/{entity}",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    # Capacity endpoints --------------------------------------------------------
    def get_temporary_currency_entitlement_count(self) -> dict[str, Any]:
        resp = self.http.get(
            "licensing/temporaryCurrencyEntitlement/count",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def get_tenant_capacity_details(self) -> dict[str, Any]:
        resp = self.http.get("licensing/tenantCapacityDetails", params=self._with_api_version())
        return self._parse_dict(resp)

    def get_environment_allocations(self, environment_id: str) -> dict[str, Any]:
        resp = self.http.get(
            f"licensing/environments/{environment_id}/allocations",
            params=self._with_api_version(),
        )
        return self._parse_dict(resp)

    def update_environment_allocations(
        self, environment_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        resp = self.http.patch(
            f"licensing/environments/{environment_id}/allocations",
            params=self._with_api_version(),
            json=payload,
        )
        return self._parse_dict(resp)

    # Operation polling ---------------------------------------------------------
    def wait_for_operation(
        self,
        operation_url: str,
        *,
        interval: float = 2.0,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        """Poll an asynchronous operation until completion."""

        from ..utils.poller import poll_until

        def get_status() -> dict[str, Any]:
            resp = self.http.get(operation_url)
            data = self._parse_dict(resp)
            if not data and resp.text:
                try:
                    payload = resp.json()
                except Exception:  # pragma: no cover - defensive fallback
                    payload = {}
                if isinstance(payload, dict):
                    data = payload
            return data

        def is_done(data: dict[str, Any]) -> bool:
            status = str(data.get("status", "")).lower()
            if status in {"succeeded", "failed", "cancelled", "canceled"}:
                return True
            return False

        return poll_until(get_status, is_done, interval=interval, timeout=timeout)


__all__ = [
    "DEFAULT_API_VERSION",
    "LicensingClient",
    "LicensingOperation",
]
