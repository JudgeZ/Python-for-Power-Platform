from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from importlib import import_module
from typing import Any, Protocol, cast

from ..config import ConfigStore, Profile
from ..errors import AuthError

logger = logging.getLogger(__name__)


class _ConfidentialClient(Protocol):
    def acquire_token_for_client(self, *, scopes: Iterable[str]) -> dict[str, Any]: ...


class _PublicClient(Protocol):
    def get_accounts(self) -> list[dict[str, Any]]: ...

    def acquire_token_silent(
        self, scopes: Iterable[str], *, account: dict[str, Any]
    ) -> dict[str, Any] | None: ...

    def acquire_token_by_refresh_token(
        self, refresh_token: str, scopes: Iterable[str]
    ) -> dict[str, Any] | None: ...

    def initiate_device_flow(self, scopes: Iterable[str]) -> dict[str, Any]: ...

    def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]: ...

    def acquire_token_interactive(self, scopes: Iterable[str]) -> dict[str, Any]: ...


class _ConfidentialClientFactory(Protocol):
    def __call__(
        self, *, client_id: str, client_credential: str, authority: str
    ) -> _ConfidentialClient: ...


class _PublicClientFactory(Protocol):
    def __call__(self, client_id: str, authority: str) -> _PublicClient: ...


class _MsalModule(Protocol):
    ConfidentialClientApplication: _ConfidentialClientFactory
    PublicClientApplication: _PublicClientFactory


def _load_msal() -> _MsalModule | None:
    try:
        module = import_module("msal")
    except ImportError:  # pragma: no cover - optional dependency not installed
        return None
    except Exception:  # pragma: no cover - unexpected import failure
        logger.exception("Failed to import msal module")
        raise
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
        profile: Profile | None = None,
        store_factory: Callable[[], ConfigStore] | None = None,
    ) -> None:
        if msal is None:
            raise AuthError("msal is not installed. Install pacx[auth] to enable Azure AD auth.")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.scopes = list(scopes)
        self.client_secret = client_secret
        self.use_device_code = use_device_code
        self.profile = profile
        self._store_factory = store_factory

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
            token_result = self._acquire_user_token(public_app)
        if not token_result or "access_token" not in token_result:
            raise AuthError(f"Failed to acquire token: {token_result}")
        self._persist_credentials(token_result)
        return str(token_result["access_token"])

    def _acquire_user_token(self, app: _PublicClient) -> dict[str, Any] | None:
        refresh_result = self._try_refresh(app)
        if refresh_result:
            return refresh_result

        accounts = app.get_accounts()
        if accounts:
            silent_result = app.acquire_token_silent(self.scopes, account=accounts[0])
            if silent_result and "access_token" in silent_result:
                logger.debug("Acquired token silently via cached account")
                return silent_result

        if self._should_use_device_code():
            logger.info("Falling back to device code flow for Azure AD token acquisition")
            flow = app.initiate_device_flow(scopes=self.scopes)
            if "user_code" not in flow:
                raise AuthError("Failed to start device flow")  # pragma: no cover
            print(flow["message"])  # pragma: no cover
            return app.acquire_token_by_device_flow(flow)

        logger.info("Falling back to interactive flow for Azure AD token acquisition")
        return app.acquire_token_interactive(scopes=self.scopes)

    def _should_use_device_code(self) -> bool:
        if self.profile is not None:
            return self.profile.use_device_code
        return self.use_device_code

    def _try_refresh(self, app: _PublicClient) -> dict[str, Any] | None:
        refresh_token = self.profile.refresh_token if self.profile else None
        if not refresh_token:
            return None
        try:
            result = app.acquire_token_by_refresh_token(refresh_token, self.scopes)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Refresh token request failed: %s", exc)
            return None
        if not result or "access_token" not in result:
            error = result.get("error") if isinstance(result, dict) else None
            if error:
                logger.info("Refresh token rejected with error: %s", error)
            else:
                logger.info("Refresh token grant returned no access token")
            return None
        logger.debug("Refresh token grant succeeded for Azure AD profile")
        return result

    def _persist_credentials(self, token_result: dict[str, Any]) -> None:
        if not self.profile:
            return
        updated = False
        access_token = token_result.get("access_token")
        if isinstance(access_token, str) and access_token:
            self.profile.access_token = access_token
            updated = True
        refresh_token = token_result.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            self.profile.refresh_token = refresh_token
            updated = True
        if not updated:
            return
        store: ConfigStore | None = None
        if self._store_factory is not None:
            try:
                store = self._store_factory()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to create config store for persistence: %s", exc)
        if store is None:
            return
        try:
            store.add_or_update_profile(self.profile)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to persist refreshed credentials: %s", exc)
