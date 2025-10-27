from __future__ import annotations

import types

import pytest

from pacx.auth.azure_ad import AzureADTokenProvider
from pacx.config import Profile


class RecordingStore:
    def __init__(self) -> None:
        self.saved_profiles: list[Profile] = []

    def add_or_update_profile(self, profile: Profile) -> Profile:
        self.saved_profiles.append(profile)
        return profile


class DummyConfidentialApp:
    def __init__(self, *, client_id: str, client_credential: str, authority: str) -> None:
        self.client_id = client_id
        self.client_secret = client_credential
        self.authority = authority
        self.requested_scopes: list[str] | None = None

    def acquire_token_for_client(self, *, scopes: list[str]) -> dict[str, str]:
        self.requested_scopes = list(scopes)
        return {"access_token": "client-cred-token"}


class RefreshFirstPublicApp:
    def __init__(self, client_id: str, authority: str) -> None:
        self.client_id = client_id
        self.authority = authority
        self.refresh_calls: list[tuple[str, list[str]]] = []
        self.device_flow_started = False
        self.interactive_calls = 0

    def get_accounts(self) -> list[dict[str, str]]:
        return []

    def acquire_token_silent(
        self, scopes: list[str], *, account: dict[str, str]
    ) -> dict[str, str] | None:
        return None

    def acquire_token_by_refresh_token(
        self, refresh_token: str, scopes: list[str]
    ) -> dict[str, str] | None:
        self.refresh_calls.append((refresh_token, list(scopes)))
        return {"access_token": "refreshed-token", "refresh_token": "rotated-refresh"}

    def initiate_device_flow(self, scopes: list[str]) -> dict[str, str]:
        self.device_flow_started = True
        return {"user_code": "XYZ", "message": "Visit example"}

    def acquire_token_by_device_flow(self, flow: dict[str, str]) -> dict[str, str]:
        return {"access_token": "device-token", "refresh_token": "device-refresh"}

    def acquire_token_interactive(self, scopes: list[str]) -> dict[str, str]:
        self.interactive_calls += 1
        return {"access_token": "interactive-token", "refresh_token": "interactive-refresh"}


class RefreshFailureDeviceApp(RefreshFirstPublicApp):
    def acquire_token_by_refresh_token(
        self, refresh_token: str, scopes: list[str]
    ) -> dict[str, str] | None:
        super().acquire_token_by_refresh_token(refresh_token, scopes)
        return {"error": "invalid_grant"}

    def acquire_token_by_device_flow(self, flow: dict[str, str]) -> dict[str, str]:
        self.device_flow_started = True
        return {"access_token": "device-token", "refresh_token": "device-refresh"}


class RefreshFailureInteractiveApp(RefreshFirstPublicApp):
    def acquire_token_by_refresh_token(
        self, refresh_token: str, scopes: list[str]
    ) -> dict[str, str] | None:
        super().acquire_token_by_refresh_token(refresh_token, scopes)
        return None

    def acquire_token_interactive(self, scopes: list[str]) -> dict[str, str]:
        self.interactive_calls += 1
        return {"access_token": "interactive-token", "refresh_token": "interactive-refresh"}


@pytest.fixture
def base_profile() -> Profile:
    return Profile(
        name="default",
        tenant_id="contoso",
        client_id="app-id",
        scope="User.Read",
        access_token=None,
        refresh_token="initial-refresh",  # noqa: S106 - deterministic test token
        use_device_code=True,
    )


def test_refresh_token_succeeds_and_persists(
    monkeypatch: pytest.MonkeyPatch, base_profile: Profile
) -> None:
    store = RecordingStore()

    module = types.SimpleNamespace(
        ConfidentialClientApplication=DummyConfidentialApp,
        PublicClientApplication=RefreshFirstPublicApp,
    )
    monkeypatch.setattr("pacx.auth.azure_ad.msal", module, raising=False)

    provider = AzureADTokenProvider(
        tenant_id=base_profile.tenant_id or "",
        client_id=base_profile.client_id or "",
        scopes=[base_profile.scope or "User.Read"],
        profile=base_profile,
        store_factory=lambda: store,
    )

    token = provider.get_token()

    assert token == "refreshed-token"  # noqa: S105 - deterministic test token
    assert base_profile.access_token == "refreshed-token"  # noqa: S105 - deterministic test token
    assert base_profile.refresh_token == "rotated-refresh"  # noqa: S105 - deterministic test token
    assert store.saved_profiles[-1] is base_profile


def test_refresh_failure_routes_to_device_flow(
    monkeypatch: pytest.MonkeyPatch, base_profile: Profile
) -> None:
    base_profile.use_device_code = True
    store = RecordingStore()

    module = types.SimpleNamespace(
        ConfidentialClientApplication=DummyConfidentialApp,
        PublicClientApplication=RefreshFailureDeviceApp,
    )
    monkeypatch.setattr("pacx.auth.azure_ad.msal", module, raising=False)

    provider = AzureADTokenProvider(
        tenant_id=base_profile.tenant_id or "",
        client_id=base_profile.client_id or "",
        scopes=[base_profile.scope or "User.Read"],
        profile=base_profile,
        store_factory=lambda: store,
    )

    token = provider.get_token()

    assert token == "device-token"  # noqa: S105 - deterministic test token
    assert base_profile.access_token == "device-token"  # noqa: S105 - deterministic test token
    assert base_profile.refresh_token == "device-refresh"  # noqa: S105 - deterministic test token
    assert store.saved_profiles[-1] is base_profile


def test_refresh_failure_routes_to_interactive_flow(
    monkeypatch: pytest.MonkeyPatch, base_profile: Profile
) -> None:
    base_profile.use_device_code = False
    store = RecordingStore()

    module = types.SimpleNamespace(
        ConfidentialClientApplication=DummyConfidentialApp,
        PublicClientApplication=RefreshFailureInteractiveApp,
    )
    monkeypatch.setattr("pacx.auth.azure_ad.msal", module, raising=False)

    provider = AzureADTokenProvider(
        tenant_id=base_profile.tenant_id or "",
        client_id=base_profile.client_id or "",
        scopes=[base_profile.scope or "User.Read"],
        profile=base_profile,
        store_factory=lambda: store,
    )

    token = provider.get_token()

    assert token == "interactive-token"  # noqa: S105 - deterministic test token
    assert base_profile.access_token == "interactive-token"  # noqa: S105 - deterministic test token
    assert base_profile.refresh_token == "interactive-refresh"  # noqa: S105
    assert store.saved_profiles[-1] is base_profile


def test_client_credentials_flow_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.SimpleNamespace(
        ConfidentialClientApplication=DummyConfidentialApp,
        PublicClientApplication=None,
    )
    monkeypatch.setattr("pacx.auth.azure_ad.msal", module, raising=False)

    provider = AzureADTokenProvider(
        tenant_id="contoso",
        client_id="app-id",
        scopes=["https://graph.microsoft.com/.default"],
        client_secret="dummy-secret",  # noqa: S106 - placeholder credential
    )

    assert provider.get_token() == "client-cred-token"
