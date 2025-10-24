from __future__ import annotations

import importlib
import sys
import types

import importlib
import sys
import types

import pytest
import typer
from typer.core import TyperCommand

from pacx.config import ConfigData, EncryptedConfigError, Profile
from pacx.errors import AuthError, HttpError


def load_common_module():
    sys.modules.pop("pacx.cli.common", None)
    return importlib.import_module("pacx.cli.common")


def make_context() -> typer.Context:
    command = TyperCommand("dummy", callback=lambda: None)
    return typer.Context(command)


def test_resolve_token_getter_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "env-token")
    module = load_common_module()

    getter = module.resolve_token_getter()

    assert getter() == "env-token"


def test_get_token_getter_builds_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    provider_kwargs: dict[str, object] = {}
    secret_calls: list[str] = []

    def fake_get_secret(spec) -> str:
        secret_calls.append(f"{spec.backend}:{spec.ref}")
        return "super-secret"

    common_module = load_common_module()
    monkeypatch.setattr(common_module, "get_secret", fake_get_secret)

    class DummyProvider:
        def __init__(self, **kwargs) -> None:
            provider_kwargs.update(kwargs)

        def get_token(self) -> str:
            return "provider-token"

    fake_module = types.ModuleType("pacx.auth.azure_ad")
    fake_module.AzureADTokenProvider = DummyProvider
    import pacx.auth as auth_pkg

    monkeypatch.setitem(sys.modules, "pacx.auth.azure_ad", fake_module)
    monkeypatch.setattr(auth_pkg, "azure_ad", fake_module, raising=False)

    config = ConfigData(
        default_profile="default",
        profiles={
            "default": Profile(
                name="default",
                tenant_id="tenant",
                client_id="client",
                scopes=["api/.default"],
                # Bandit B106: identifies backend implementation.
                secret_backend="keyring",  # nosec B106
                # Bandit B106: pointer to stored secret.
                secret_ref="svc:user",  # nosec B106
            )
        },
    )

    monkeypatch.setattr(common_module, "get_config_from_context", lambda ctx, store=None: config)

    ctx = make_context()
    getter = common_module.get_token_getter(ctx)

    result = getter()
    assert result == "provider-token"
    assert secret_calls == ["keyring:svc:user"]
    assert provider_kwargs.get("client_secret") == "super-secret"
    # Token getter should be cached on the context object.
    assert common_module.get_token_getter(ctx) is getter


def test_get_token_getter_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    def failing_resolve(*_, **__):
        raise typer.BadParameter("no token")

    common_module = load_common_module()
    monkeypatch.setattr(common_module, "resolve_token_getter", failing_resolve)
    ctx = make_context()

    assert common_module.get_token_getter(ctx, required=False) is None


def test_handle_cli_errors_http(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    common_module = load_common_module()
    monkeypatch.setattr(
        common_module,
        "console",
        types.SimpleNamespace(
            print=lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args))
        ),
    )

    handler = common_module.handle_cli_errors

    @handler
    def command():
        raise HttpError(400, "Bad", details={"error": "missing"})

    with pytest.raises(typer.Exit) as exc_info:
        command()

    assert exc_info.value.exit_code == 1
    assert any("HTTP 400" in msg for msg in messages)
    assert any("error" in msg for msg in messages)


def test_handle_cli_errors_encrypted_config(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    common_module = load_common_module()
    monkeypatch.setattr(
        common_module,
        "console",
        types.SimpleNamespace(
            print=lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args))
        ),
    )

    handler = common_module.handle_cli_errors

    @handler
    def command():
        raise EncryptedConfigError("missing key")

    with pytest.raises(typer.Exit):
        command()

    assert any("Restore the original key" in msg for msg in messages)


def test_handle_cli_errors_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    common_module = load_common_module()
    monkeypatch.setattr(
        common_module,
        "console",
        types.SimpleNamespace(
            print=lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args))
        ),
    )

    handler = common_module.handle_cli_errors

    @handler
    def command():
        raise AuthError("expired")

    with pytest.raises(typer.Exit):
        command()

    assert any("Authentication failed" in msg for msg in messages)


def test_handle_cli_errors_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    monkeypatch.delenv("PACX_DEBUG", raising=False)
    common_module = load_common_module()
    monkeypatch.setattr(
        common_module,
        "console",
        types.SimpleNamespace(
            print=lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args))
        ),
    )

    handler = common_module.handle_cli_errors

    @handler
    def command():
        raise RuntimeError("boom")

    with pytest.raises(typer.Exit):
        command()

    assert any("Unexpected failure" in msg for msg in messages)


def test_handle_cli_errors_debug_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACX_DEBUG", "1")

    handler = load_common_module().handle_cli_errors

    @handler
    def command():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        command()
