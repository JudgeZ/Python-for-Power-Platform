from __future__ import annotations

import os
from collections.abc import Callable

import pytest

from pacx.cli.common import resolve_access_token

TokenSource = Callable[[], str | None]


def _clear_env(var: str = "PACX_ACCESS_TOKEN") -> None:
    os.environ.pop(var, None)


def test_env_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "env-token")

    called: list[str] = []

    def secret() -> str | None:  # pragma: no cover - should not be called
        called.append("secret")
        return "secret-token"

    resolved = resolve_access_token(
        get_secret_token=secret,
        get_config_token=lambda: "config-token",
        get_provider_token=lambda: "provider-token",
    )
    assert resolved == "env-token"
    assert called == []
    _clear_env()


def test_secret_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env()
    resolved = resolve_access_token(
        get_secret_token=lambda: "secret-token",
        get_config_token=lambda: "config-token",
        get_provider_token=lambda: "provider-token",
    )
    assert resolved == "secret-token"


def test_config_when_env_and_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env()
    resolved = resolve_access_token(
        get_secret_token=lambda: None,
        get_config_token=lambda: "config-token",
        get_provider_token=lambda: "provider-token",
    )
    assert resolved == "config-token"


def test_provider_when_others_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env()
    resolved = resolve_access_token(
        get_secret_token=lambda: None,
        get_config_token=lambda: None,
        get_provider_token=lambda: "provider-token",
    )
    assert resolved == "provider-token"


def test_none_when_all_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env()
    resolved = resolve_access_token(
        get_secret_token=lambda: None,
        get_config_token=lambda: None,
        get_provider_token=lambda: None,
    )
    assert resolved is None
