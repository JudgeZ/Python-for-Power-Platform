from __future__ import annotations

import types

import pytest

from pacx.auth.azure_ad import AzureADTokenProvider, msal as original_msal
from pacx.auth.base import StaticTokenProvider
from pacx.errors import AuthError


class StubConfidentialApp:
    def __init__(self, *, client_id: str, client_credential: str, authority: str) -> None:
        self.client_id = client_id
        self.client_secret = client_credential
        self.authority = authority
        self.requested_scopes: list[str] | None = None

    def acquire_token_for_client(self, *, scopes: list[str]) -> dict[str, str]:
        self.requested_scopes = list(scopes)
        return {"access_token": "confidential-token"}


class StubPublicApp:
    def __init__(self, client_id: str, authority: str) -> None:
        self.client_id = client_id
        self.authority = authority
        self.flows: list[dict[str, str]] = []
        self.device_flow_started = False

    def get_accounts(self) -> list[dict[str, str]]:
        return []

    def acquire_token_silent(
        self, scopes: list[str], *, account: dict[str, str]
    ) -> dict[str, str] | None:
        return None

    def initiate_device_flow(self, scopes: list[str]) -> dict[str, str]:
        self.device_flow_started = True
        return {"user_code": "ABC", "message": "Go to example"}

    def acquire_token_by_device_flow(self, flow: dict[str, str]) -> dict[str, str]:
        self.flows.append(flow)
        return {"access_token": "device-token"}


@pytest.fixture
def stub_msal(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    module = types.SimpleNamespace(
        ConfidentialClientApplication=StubConfidentialApp,
        PublicClientApplication=StubPublicApp,
    )
    monkeypatch.setattr("pacx.auth.azure_ad.msal", module, raising=False)
    return module


def test_static_token_provider_returns_constant() -> None:
    provider = StaticTokenProvider("abc123")
    assert provider.get_token() == "abc123"


def test_azure_ad_token_provider_confidential_flow(stub_msal: types.SimpleNamespace) -> None:
    provider = AzureADTokenProvider(
        tenant_id="contoso",
        client_id="app-id",
        scopes=["https://graph.microsoft.com/.default"],
        # Bandit B106: placeholder credential for test double.
        client_secret="dummy-secret",  # nosec B106
    )
    token = provider.get_token()
    # Bandit B105: deterministic stub output.
    assert token == "confidential-token"  # nosec B105


def test_azure_ad_token_provider_device_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = types.SimpleNamespace(
        ConfidentialClientApplication=StubConfidentialApp,
        PublicClientApplication=StubPublicApp,
    )
    monkeypatch.setattr("pacx.auth.azure_ad.msal", stub, raising=False)

    provider = AzureADTokenProvider(
        tenant_id="contoso",
        client_id="app-id",
        scopes=["User.Read"],
        client_secret=None,
        use_device_code=True,
    )
    token = provider.get_token()
    # Bandit B105: deterministic stub output.
    assert token == "device-token"  # nosec B105


def test_azure_ad_token_provider_requires_msal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pacx.auth.azure_ad.msal", None, raising=False)
    try:
        with pytest.raises(AuthError):
            AzureADTokenProvider(
                tenant_id="contoso",
                client_id="app-id",
                scopes=["User.Read"],
            )
    finally:
        monkeypatch.setattr("pacx.auth.azure_ad.msal", original_msal, raising=False)
