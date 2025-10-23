from __future__ import annotations

import json
import os
from functools import wraps
from typing import Callable, Optional

import typer
from rich.console import Console

from ..cli_utils import get_config_from_context
from ..config import ConfigData, ConfigStore, EncryptedConfigError
from ..errors import AuthError, HttpError, PacxError
from ..secrets import SecretSpec, get_secret

console = Console()


def _render_http_error(exc: HttpError) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    details = getattr(exc, "details", None)
    if details:
        snippet = details
        if isinstance(details, dict):
            snippet = json.dumps(details, indent=2)
        console.print(str(snippet))


def handle_cli_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except typer.BadParameter:
            raise
        except typer.Exit:
            raise
        except HttpError as exc:
            _render_http_error(exc)
            raise typer.Exit(1) from None
        except EncryptedConfigError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            console.print(
                "Restore the original key by exporting PACX_CONFIG_ENCRYPTION_KEY before rerunning the command."
            )
            console.print(
                "If the key is lost, back up and remove the encrypted config (default ~/.pacx/config.json) then run `ppx auth device` to recreate credentials."
            )
            raise typer.Exit(1) from None
        except AuthError as exc:
            console.print(f"[red]Error:[/red] Authentication failed: {exc}")
            console.print("Run `ppx auth device` or `ppx auth secret` to refresh credentials.")
            raise typer.Exit(1) from None
        except PacxError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1) from None
        except Exception as exc:
            if os.getenv("PACX_DEBUG"):
                raise
            console.print(f"[red]Error:[/red] Unexpected failure: {exc}")
            console.print("Set PACX_DEBUG=1 for a stack trace.")
            raise typer.Exit(1) from exc

    return wrapper


TokenGetter = Callable[[], str]


def resolve_token_getter(config: ConfigData | None = None) -> TokenGetter:
    token = os.getenv("PACX_ACCESS_TOKEN")
    if token:
        return lambda: token

    cfg = config or ConfigStore().load()
    if cfg.default_profile and cfg.profiles and cfg.default_profile in cfg.profiles:
        try:
            from ..auth.azure_ad import AzureADTokenProvider
        except Exception as exc:  # pragma: no cover
            raise typer.BadParameter(
                "msal not installed; install pacx[auth] or set PACX_ACCESS_TOKEN"
            ) from exc
        profile = cfg.profiles[cfg.default_profile]
        client_secret = None
        if getattr(profile, "client_secret_env", None):
            client_secret = os.getenv(profile.client_secret_env)
        if (
            getattr(profile, "secret_backend", None)
            and getattr(profile, "secret_ref", None)
            and not client_secret
        ):
            secret = get_secret(SecretSpec(backend=profile.secret_backend, ref=profile.secret_ref))
            if secret:
                client_secret = secret
        provider = AzureADTokenProvider(
            tenant_id=profile.tenant_id,
            client_id=profile.client_id,
            scopes=[profile.scope],
            client_secret=client_secret,
            use_device_code=(client_secret is None),
        )
        return provider.get_token
    raise typer.BadParameter("No PACX_ACCESS_TOKEN and no default profile configured.")


def get_token_getter(ctx: typer.Context, *, required: bool = True) -> Optional[TokenGetter]:
    ctx.ensure_object(dict)
    token_getter = ctx.obj.get("token_getter") if ctx.obj else None
    if callable(token_getter):
        return token_getter

    if token_getter is None:
        config: ConfigData | None = None
        if not os.getenv("PACX_ACCESS_TOKEN"):
            config = get_config_from_context(ctx)
        try:
            token_getter = resolve_token_getter(config=config)
        except typer.BadParameter:
            if not required:
                return None
            raise
        ctx.obj["token_getter"] = token_getter
    return token_getter


__all__ = ["console", "handle_cli_errors", "resolve_token_getter", "get_token_getter", "TokenGetter"]
