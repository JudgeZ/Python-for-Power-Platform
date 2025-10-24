from __future__ import annotations

from collections.abc import Iterable
from importlib import import_module
from typing import Any, Protocol, cast

from ..errors import AuthError


class _ConfidentialClient(Protocol):
    def acquire_token_for_client(self, *, scopes: Iterable[str]) -> dict[str, Any]:
        ...


class _PublicClient(Protocol):
    def get_accounts(self) -> list[dict[str, Any]]:
        ...

    def acquire_token_silent(
        self, scopes: Iterable[str], *, account: dict[str, Any]
    ) -> dict[str, Any] | None:
        ...

    def initiate_device_flow(self, scopes: Iterable[str]) -> dict[str, Any]:
        ...

    def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
        ...


class _ConfidentialClientFactory(Protocol):
    def __call__(self, *, client_id: str, client_credential: str, authority: str) -> _ConfidentialClient:
        ...


class _PublicClientFactory(Protocol):
    def __call__(self, client_id: str, authority: str) -> _PublicClient:
        ...


class _MsalModule(Protocol):
    ConfidentialClientApplication: _ConfidentialClientFactory
    PublicClientApplication: _PublicClientFactory


def _load_msal() -> _MsalModule | None:
    try:
        module = import_module("msal")
    except Exception:  # pragma: no cover - optional dependency not installed
        return None
    return cast(_MsalModule, module)


msal = _load_msal()


class AzureADTokenProvider:
    """MSAL-based provider supporting device code or client credentials."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        scopes: Iterable[str],
        client_secret: str | None = None,
        use_device_code: bool = False,
    ) -> None:
        if msal is None:
            raise AuthError("msal is not installed. Install pacx[auth] to enable Azure AD auth.")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.scopes = list(scopes)
        self.client_secret = client_secret
        self.use_device_code = use_device_code

    def get_token(self) -> str:
        msal_module = cast(_MsalModule, msal)
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        token_result: dict[str, Any] | None
        if self.client_secret:
            confidential_app = msal_module.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=authority,
            )
            token_result = confidential_app.acquire_token_for_client(scopes=self.scopes)
        else:
            public_app = msal_module.PublicClientApplication(self.client_id, authority=authority)
            accounts = public_app.get_accounts()
            token_result = (
                public_app.acquire_token_silent(self.scopes, account=accounts[0]) if accounts else None
            )
            if not token_result:
                if self.use_device_code:
                    flow = public_app.initiate_device_flow(scopes=self.scopes)
                    if "user_code" not in flow:
                        raise AuthError("Failed to start device flow")  # pragma: no cover
                    print(flow["message"])  # pragma: no cover
                    token_result = public_app.acquire_token_by_device_flow(flow)
                else:
                    raise AuthError(
                        "Interactive auth not configured; set use_device_code=True or provide client_secret."
                    )
        if not token_result or "access_token" not in token_result:
            raise AuthError(f"Failed to acquire token: {token_result}")
        return str(token_result["access_token"])
