from __future__ import annotations

import typer
from rich import print

from ..config import ConfigStore, Profile
from .common import handle_cli_errors

KEYRING_BACKEND = "keyring"
KEYVAULT_BACKEND = "keyvault"

app = typer.Typer(help="Authentication and profiles")


@app.command("device")
@handle_cli_errors
def auth_device(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    scope: str = typer.Option(
        "https://api.powerplatform.com/.default", help="Scope (default: PP API)"
    ),
    dataverse_host: str | None = typer.Option(None, help="Default DV host for this profile"),
):
    """Create/update a device-code profile. Token acquisition happens on use."""
    store = ConfigStore()
    profile = Profile(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scope=scope,
        dataverse_host=dataverse_host,
    )
    store.add_or_update_profile(profile)
    store.set_default_profile(name)
    print(f"Profile [bold]{name}[/bold] configured. It will use device code on demand.")


@app.command("client")
@handle_cli_errors
def auth_client(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    client_secret_env: str | None = typer.Option(
        None, help="Name of env var holding the client secret (env backend)"
    ),
    secret_backend: str | None = typer.Option(None, help="Secret backend: env|keyring|keyvault"),
    secret_ref: str | None = typer.Option(
        None, help="Backend ref: ENV_VAR or service:username or VAULT_URL:SECRET"
    ),
    prompt_secret: bool = typer.Option(
        False, help="For keyring: prompt and store a secret under service:username"
    ),
    scope: str = typer.Option(
        "https://api.powerplatform.com/.default", help="Scope (default: PP API)"
    ),
    dataverse_host: str | None = typer.Option(None, help="Default DV host for this profile"),
):
    """Create/update a client-credentials profile (secret read from env var on use)."""
    store = ConfigStore()
    profile = Profile(
        name=name,
        tenant_id=tenant_id,
        client_id=client_id,
        scope=scope,
        dataverse_host=dataverse_host,
        client_secret_env=client_secret_env,
    )
    backend = secret_backend
    if backend:
        profile.secret_backend = backend
        if secret_ref:
            profile.secret_ref = secret_ref
        if backend == KEYRING_BACKEND and prompt_secret:
            try:
                import keyring

                if not secret_ref or ":" not in secret_ref:
                    raise typer.BadParameter("--secret-ref must be 'SERVICE:USERNAME' for keyring")
                service, username = secret_ref.split(":", 1)
                value = typer.prompt(f"Enter secret for {service}:{username}", hide_input=True)
                keyring.set_password(service, username, value)
                print("Stored secret in keyring.")
            except Exception as exc:
                print(f"[yellow]Keyring not available or failed: {exc}[/yellow]")
        if backend == KEYVAULT_BACKEND and not secret_ref:
            print("[yellow]Provide --secret-ref 'VAULT_URL:SECRET_NAME' for Key Vault[/yellow]")
    store.add_or_update_profile(profile)
    store.set_default_profile(name)
    where = backend or ("env" if client_secret_env else "device")
    print(f"Client-credentials profile [bold]{name}[/bold] configured. Backend: {where}")


@app.command("use")
@handle_cli_errors
def auth_use(name: str = typer.Argument(..., help="Profile to activate")):
    store = ConfigStore()
    store.set_default_profile(name)
    print(f"Default profile set to [bold]{name}[/bold]")


__all__ = ["app", "auth_device", "auth_client", "auth_use"]
