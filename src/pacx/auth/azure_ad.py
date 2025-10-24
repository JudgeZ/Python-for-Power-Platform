from __future__ import annotations

from collections.abc import Iterable

from ..errors import AuthError

try:
    import msal  # type: ignore
except Exception:  # pragma: no cover
    msal = None  # type: ignore


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
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        if self.client_secret:
            app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=authority,
            )
            result = app.acquire_token_for_client(scopes=self.scopes)
        else:
            app = msal.PublicClientApplication(self.client_id, authority=authority)
            accounts = app.get_accounts()
            result = None
            if accounts:
                result = app.acquire_token_silent(self.scopes, account=accounts[0])
            if not result:
                if self.use_device_code:
                    flow = app.initiate_device_flow(scopes=self.scopes)
                    if "user_code" not in flow:
                        raise AuthError("Failed to start device flow")  # pragma: no cover
                    print(flow["message"])  # pragma: no cover
                    result = app.acquire_token_by_device_flow(flow)
                else:
                    raise AuthError(
                        "Interactive auth not configured; set use_device_code=True or provide client_secret."
                    )
        if "access_token" not in result:
            raise AuthError(f"Failed to acquire token: {result}")
        return result["access_token"]
