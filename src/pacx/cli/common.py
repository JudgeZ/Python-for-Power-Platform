from __future__ import annotations

import json
import os
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, Literal, ParamSpec, TypeVar, cast, overload

import typer
from rich.console import Console

from ..cli_utils import get_config_from_context
from ..config import ConfigData, ConfigStore, EncryptedConfigError
from ..errors import AuthError, HttpError, PacxError
from ..secrets import SecretSpec, get_secret

if TYPE_CHECKING:
    from ..auth.azure_ad import AzureADTokenProvider

console = Console()


def _render_http_error(exc: HttpError) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    details = getattr(exc, "details", None)
    if details:
        snippet = details
        if isinstance(details, dict):
            snippet = json.dumps(details, indent=2)
        console.print(str(snippet))


CommandParams = ParamSpec("CommandParams")
CommandReturn = TypeVar("CommandReturn")


def handle_cli_errors(
    func: Callable[CommandParams, CommandReturn],
) -> Callable[CommandParams, CommandReturn]:
    @wraps(func)
    def wrapper(*args: CommandParams.args, **kwargs: CommandParams.kwargs) -> CommandReturn:
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
                "If the key is lost, back up and remove the encrypted config (default ~/.pacx/config.json) then run `ppx auth create NAME --flow device` to recreate credentials."
            )
            raise typer.Exit(1) from None
        except AuthError as exc:
            console.print(f"[red]Error:[/red] Authentication failed: {exc}")
            console.print(
                "Run `ppx auth create NAME --flow device` or `ppx auth create NAME --flow client-credential` to refresh credentials."
            )
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
TokenSource = Callable[[], str | None]


def resolve_token_getter(config: ConfigData | None = None) -> TokenGetter:
    """Resolve a callable that returns an access token.

    Resolution order is:

    1. Explicit environment override via ``PACX_ACCESS_TOKEN``.
    2. Token secrets sourced from a configured backend (``token_backend``/``token_ref``).
    3. Cached token stored in the encrypted config file.
    4. Refresh/interactive acquisition via :class:`AzureADTokenProvider`.
    """

    token = os.getenv("PACX_ACCESS_TOKEN")
    if token:

        def env_getter() -> str:
            override = os.getenv("PACX_ACCESS_TOKEN")
            return override or token

        return env_getter

    cfg = config or ConfigStore().load()
    if not (cfg.default_profile and cfg.profiles and cfg.default_profile in cfg.profiles):
        raise typer.BadParameter("No PACX_ACCESS_TOKEN and no default profile configured.")

    profile = cfg.profiles[cfg.default_profile]
    tenant_id = profile.tenant_id
    client_id = profile.client_id
    if not tenant_id or not client_id:
        raise typer.BadParameter(
            "Profile is missing tenant_id or client_id; run `ppx profile update` to fix."
        )
    scope = profile.scope
    scopes = profile.scopes
    scope_values: list[str]
    if scope:
        scope_values = [scope]
    elif scopes:
        scope_values = list(scopes)
    else:
        raise typer.BadParameter(
            "Profile missing scopes; set scope or scopes on the default profile."
        )

    client_secret = None
    client_secret_env = profile.client_secret_env
    if client_secret_env:
        client_secret = os.getenv(client_secret_env)
    secret_backend = profile.secret_backend
    secret_ref = profile.secret_ref
    if secret_backend and secret_ref and not client_secret:
        secret = get_secret(SecretSpec(backend=secret_backend, ref=secret_ref))
        if secret:
            client_secret = secret
    raw_use_device_code = getattr(profile, "use_device_code", None)
    legacy_device_code = bool(getattr(profile, "_legacy_device_code_default", False))
    if raw_use_device_code is None:
        use_device_code = client_secret is None
    elif legacy_device_code and client_secret is None:
        use_device_code = True
    else:
        use_device_code = bool(raw_use_device_code)

    token_backend = getattr(profile, "token_backend", None)
    token_ref = getattr(profile, "token_ref", None)
    token_spec: SecretSpec | None = None
    if token_backend and token_ref:
        token_spec = SecretSpec(backend=str(token_backend), ref=str(token_ref))

    provider: AzureADTokenProvider | None = None

    def _get_provider() -> AzureADTokenProvider:
        nonlocal provider
        if provider is None:
            try:
                from ..auth.azure_ad import AzureADTokenProvider
            except Exception as exc:  # pragma: no cover
                raise typer.BadParameter(
                    "msal not installed; install pacx[auth] or set PACX_ACCESS_TOKEN"
                ) from exc
            provider = AzureADTokenProvider(
                tenant_id=tenant_id,
                client_id=client_id,
                scopes=scope_values,
                client_secret=client_secret,
                use_device_code=use_device_code,
                profile=profile,
                store_factory=ConfigStore,
            )
        return provider

    def getter() -> str:
        override = os.getenv("PACX_ACCESS_TOKEN")
        if override:
            return override
        if token_spec is not None:
            secret_token = get_secret(token_spec)
            if secret_token:
                return secret_token
        cached_token = profile.access_token
        if cached_token:
            return cached_token
        result = _get_provider().get_token()
        # Provider persists refreshed credentials back onto the profile.
        if profile.access_token:
            return profile.access_token
        return result

    return getter


@overload
def get_token_getter(ctx: typer.Context, *, required: Literal[True] = ...) -> TokenGetter: ...


@overload
def get_token_getter(ctx: typer.Context, *, required: Literal[False]) -> TokenGetter | None: ...


def get_token_getter(ctx: typer.Context, *, required: bool = True) -> TokenGetter | None:
    ctx_obj = cast(dict[str, Any], ctx.ensure_object(dict))
    token_getter = ctx_obj.get("token_getter")
    if callable(token_getter):
        return cast(TokenGetter, token_getter)

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
        ctx_obj["token_getter"] = token_getter
    if token_getter is None:
        if required:
            raise typer.BadParameter("Token getter is required but could not be resolved.")
        return None
    return cast(TokenGetter, token_getter)


__all__ = [
    "console",
    "handle_cli_errors",
    "resolve_token_getter",
    "get_token_getter",
    "TokenGetter",
    "resolve_access_token",
]


def resolve_access_token(
    *,
    get_secret_token: TokenSource | None = None,
    get_config_token: TokenSource | None = None,
    get_provider_token: TokenSource | None = None,
    env_var: str = "PACX_ACCESS_TOKEN",
) -> str | None:
    """Resolve an access token using injectable sources.

    Precedence:
    1) Environment variable (``env_var``)
    2) ``get_secret_token`` (e.g., keyring/KeyVault) if provided
    3) ``get_config_token`` (encrypted config) if provided
    4) ``get_provider_token`` (refresh/interactive) if provided

    The helper is intentionally pure and side‑effect free: it does not import
    backends, print output, or mutate configuration. Callers supply the
    callables for each source. Returns the first non‑empty token or ``None``.
    """

    token = os.getenv(env_var)
    if token:
        token = token.strip()
        if token:
            return token

    if get_secret_token is not None:
        token = get_secret_token() or None
        if token:
            return token

    if get_config_token is not None:
        token = get_config_token() or None
        if token:
            return token

    if get_provider_token is not None:
        token = get_provider_token() or None
        if token:
            return token

    return None
