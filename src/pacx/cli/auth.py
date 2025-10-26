from __future__ import annotations

"""Authentication-related Typer commands and their signatures."""

import re
from typing import Literal, Sequence, cast

import typer
from rich import print

from ..config import ConfigStore, Profile
from .common import handle_cli_errors

KEYRING_BACKEND = "keyring"
KEYVAULT_BACKEND = "keyvault"
DEFAULT_SCOPE = "https://api.powerplatform.com/.default"

FlowType = Literal["device", "web", "client-credential"]

app = typer.Typer(help="Authentication and profiles")


def _ensure_secret_reference(secret_ref: str | None) -> tuple[str, str]:
    if not secret_ref or ":" not in secret_ref:
        raise typer.BadParameter(
            "--secret-ref must use 'SERVICE:USERNAME' when --secret-backend=keyring"
        )
    service, username = secret_ref.split(":", 1)
    return service, username


def _prompt_and_store_keyring_secret(secret_ref: str) -> None:
    try:  # pragma: no cover - defensive import guard exercised in tests
        import keyring
    except Exception as exc:  # pragma: no cover - fallback message for missing keyring
        print(f"[yellow]Keyring not available or failed: {exc}[/yellow]")
        return

    service, username = _ensure_secret_reference(secret_ref)
    value = typer.prompt(f"Enter secret for {service}:{username}", hide_input=True)
    keyring.set_password(service, username, value)
    print("Stored secret in keyring.")


def _normalize_scopes(scopes: Sequence[str]) -> list[str]:
    values = [scope.strip() for scope in scopes if scope and scope.strip()]
    if not values:
        raise typer.BadParameter("Provide at least one --scope value.")
    return values


def _parse_scope_values(raw_scope: str) -> list[str]:
    separators = re.compile(r"[\s,]+")
    parts = separators.split(raw_scope or "")
    return [part for part in parts if part]


def _build_profile(
    *,
    name: str,
    tenant_id: str,
    client_id: str,
    scopes: Sequence[str],
    dataverse_host: str | None,
    flow: FlowType,
    client_secret_env: str | None,
    secret_backend: str | None,
    secret_ref: str | None,
    prompt_secret: bool,
) -> Profile:
    scope_values = _normalize_scopes(scopes)
    primary_scope = scope_values[0]
    profile = Profile(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scope=primary_scope,
        scopes=scope_values,
        dataverse_host=dataverse_host,
        use_device_code=flow == "device",
    )

    if flow == "client-credential":
        profile.use_device_code = False
        profile.client_secret_env = client_secret_env
        profile.secret_backend = secret_backend
        profile.secret_ref = secret_ref
        if secret_backend == KEYRING_BACKEND and prompt_secret:
            _prompt_and_store_keyring_secret(secret_ref or "")
        if secret_backend == KEYVAULT_BACKEND and not secret_ref:
            print("[yellow]Provide --secret-ref 'VAULT_URL:SECRET_NAME' for Key Vault[/yellow]")
    elif client_secret_env or secret_backend or secret_ref:
        print(
            "[yellow]Secret options are ignored unless --flow client-credential is selected.[/yellow]"
        )

    if flow == "web":
        profile.use_device_code = False

    return profile


def _persist_profile(profile: Profile, *, set_default: bool) -> None:
    store = ConfigStore()
    before = store.load()
    previous_default = before.default_profile
    cfg = store.add_or_update_profile(profile, set_default=set_default)
    new_default = cfg.default_profile
    default_now_profile = new_default == profile.name

    if default_now_profile and (set_default or previous_default is None):
        print(
            f"Profile [bold]{profile.name}[/bold] configured and set as the default profile."
        )
        return

    if set_default and not default_now_profile:
        print(
            f"Profile [bold]{profile.name}[/bold] configured. Existing default left unchanged."
        )
        return

    if not set_default and default_now_profile:
        print(
            f"Profile [bold]{profile.name}[/bold] configured and promoted to default because none was set."
        )
        return

    print(
        f"Profile [bold]{profile.name}[/bold] configured. Default profile not modified."
    )


def _render_flow_summary(flow: FlowType, secret_backend: str | None) -> str:
    if flow == "client-credential":
        backend = secret_backend or "environment variables"
        return f"client credentials via {backend}"
    if flow == "web":
        return "interactive browser flow"
    return "device code flow"


@app.command("create")
@handle_cli_errors
def auth_create(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    scope: str = typer.Option(
        DEFAULT_SCOPE,
        "--scope",
        "-s",
        help="Scopes requested during authentication (comma or space separated).",
        show_default=False,
        rich_help_panel="Authentication",
        metavar="SCOPE",
    ),
    flow: FlowType = typer.Option(
        "device",
        case_sensitive=False,
        help="Authentication flow: device, web, or client-credential.",
        rich_help_panel="Authentication",
    ),
    dataverse_host: str | None = typer.Option(
        None, help="Default Dataverse host for this profile"
    ),
    client_secret_env: str | None = typer.Option(
        None, help="Environment variable containing the client secret"
    ),
    secret_backend: str | None = typer.Option(
        None,
        help="Secret backend for client credentials (env, keyring, keyvault)",
    ),
    secret_ref: str | None = typer.Option(
        None,
        help="Backend reference: ENV_VAR, service:username, or VAULT_URL:SECRET_NAME",
    ),
    prompt_secret: bool = typer.Option(
        False,
        help="Prompt for a secret and store it in keyring when --secret-backend=keyring",
    ),
    set_default: bool = typer.Option(
        True,
        "--set-default/--no-set-default",
        help="Set the profile as default after creation.",
    ),
) -> None:
    """Create or update an authentication profile."""

    flow_normalized = cast(FlowType, flow.lower())
    scope_values = _normalize_scopes(_parse_scope_values(scope))

    profile = _build_profile(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scopes=scope_values,
        dataverse_host=dataverse_host,
        flow=flow_normalized,
        client_secret_env=client_secret_env,
        secret_backend=secret_backend,
        secret_ref=secret_ref,
        prompt_secret=prompt_secret,
    )
    _persist_profile(profile, set_default=set_default)
    summary = _render_flow_summary(flow_normalized, secret_backend)
    print(f"Profile [bold]{name}[/bold] ready for {summary}.")


@app.command("use")
@handle_cli_errors
def auth_use(name: str = typer.Argument(..., help="Profile to activate")) -> None:
    """Set a profile as the default for subsequent CLI commands."""

    store = ConfigStore()
    store.set_default_profile(name)
    print(f"Default profile set to [bold]{name}[/bold]")


@app.command("device")
@handle_cli_errors
def auth_device(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    scope: str = typer.Option(
        DEFAULT_SCOPE, help="Scope (default: Power Platform API scope)"
    ),
    dataverse_host: str | None = typer.Option(
        None, help="Default Dataverse host for this profile"
    ),
) -> None:
    """Deprecated alias for ``ppx auth create --flow device``."""

    print(
        "[yellow]Deprecated:[/yellow] Run `ppx auth create"  # nosec B105 - messaging only
        " NAME --tenant-id TENANT --client-id CLIENT --flow device` instead."
    )
    auth_create(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scope=scope,
        flow="device",
        dataverse_host=dataverse_host,
    )


@app.command("client")
@handle_cli_errors
def auth_client(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    client_secret_env: str | None = typer.Option(
        None, help="Name of env var holding the client secret (env backend)"
    ),
    secret_backend: str | None = typer.Option(
        None, help="Secret backend: env|keyring|keyvault"
    ),
    secret_ref: str | None = typer.Option(
        None, help="Backend ref: ENV_VAR or service:username or VAULT_URL:SECRET"
    ),
    prompt_secret: bool = typer.Option(
        False, help="For keyring: prompt and store a secret under service:username"
    ),
    scope: str = typer.Option(
        DEFAULT_SCOPE, help="Scope (default: Power Platform API scope)"
    ),
    dataverse_host: str | None = typer.Option(
        None, help="Default Dataverse host for this profile"
    ),
) -> None:
    """Deprecated alias for ``ppx auth create --flow client-credential``."""

    print(
        "[yellow]Deprecated:[/yellow] Run `ppx auth create NAME --flow client-credential` "
        "with secret options instead."
    )
    auth_create(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scope=scope,
        flow="client-credential",
        dataverse_host=dataverse_host,
        client_secret_env=client_secret_env,
        secret_backend=secret_backend,
        secret_ref=secret_ref,
        prompt_secret=prompt_secret,
    )


__all__ = ["app", "auth_create", "auth_device", "auth_client", "auth_use"]
