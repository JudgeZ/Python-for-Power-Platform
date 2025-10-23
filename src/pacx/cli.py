
from __future__ import annotations

import base64
import json
import logging
import os
from functools import wraps
from pathlib import Path

import typer
from rich import print
from rich.console import Console

from .bulk_csv import bulk_csv_upsert
from .cli_utils import resolve_dataverse_host, resolve_environment_id
from .clients.connectors import ConnectorsClient
from .clients.dataverse import DataverseClient
from .clients.power_pages import PowerPagesClient
from .clients.power_platform import PowerPlatformClient
from .config import ConfigStore, Profile
from .errors import AuthError, HttpError, PacxError
from .models.dataverse import ExportSolutionRequest, ImportSolutionRequest
from .power_pages.diff import diff_permissions
from .secrets import SecretSpec, get_secret
from .solution_sp import pack_from_source, unpack_to_source

console = Console()
logger = logging.getLogger(__name__)

BINARY_PROVIDER_OPTION = typer.Option(
    None, "--binary-provider", help="Explicit binary providers to run"
)
KEYRING_BACKEND = "keyring"
KEYVAULT_BACKEND = "keyvault"


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


app = typer.Typer(help="PACX CLI")
auth_app = typer.Typer(help="Authentication and profiles")
profile_app = typer.Typer(help="Profiles & configuration")
dv_app = typer.Typer(help="Dataverse operations")
connector_app = typer.Typer(help="Connectors (APIs)")
app.add_typer(auth_app, name="auth")
app.add_typer(profile_app, name="profile")
app.add_typer(dv_app, name="dv")
app.add_typer(connector_app, name="connector")
pages_app = typer.Typer(help="Power Pages site ops")
app.add_typer(pages_app, name="pages")


@app.command("doctor")
@handle_cli_errors
def doctor(
    ctx: typer.Context,
    host: str | None = typer.Option(None, help="Dataverse host to probe"),
    check_dataverse: bool = typer.Option(True, help="Attempt Dataverse connectivity test"),
):
    """Validate PACX environment configuration."""

    cfg = ConfigStore().load()
    ok = True
    if cfg.default_profile:
        print(f"[green]Default profile:[/green] {cfg.default_profile}")
    else:
        print("[yellow]No default profile configured.[/yellow]")
    try:
        token_getter = _resolve_token_getter()
        token_preview = token_getter()
        print("[green]Token acquisition successful.[/green]")
        ctx.obj = {"token_getter": lambda: token_preview}
    except Exception as exc:  # pragma: no cover - error path tested separately
        print(f"[red]Token acquisition failed:[/red] {exc}")
        ok = False
        token_getter = None

    if check_dataverse and token_getter:
        hv = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
        if not hv:
            print("[yellow]Skipping Dataverse probe: host unknown.[/yellow]")
        else:
            try:
                dv = DataverseClient(lambda: token_preview, host=hv)
                who = dv.whoami()
                print(f"[green]Dataverse reachable:[/green] {who.get('UserId', 'unknown')}")
            except Exception as exc:  # pragma: no cover - network failures
                print(f"[red]Dataverse probe failed:[/red] {exc}")
                ok = False

    raise typer.Exit(code=0 if ok else 1)


def _resolve_token_getter() -> callable:
    token = os.getenv("PACX_ACCESS_TOKEN")
    if token:
        return lambda: token

    # Attempt profile-based resolution (MSAL on-demand)
    store = ConfigStore()
    cfg = store.load()
    if cfg.default_profile and cfg.profiles and cfg.default_profile in cfg.profiles:
        try:
            from .auth.azure_ad import AzureADTokenProvider  # optional dependency
        except Exception as e:  # pragma: no cover
            raise typer.BadParameter("msal not installed; install pacx[auth] or set PACX_ACCESS_TOKEN") from e
        p = cfg.profiles[cfg.default_profile]
        from os import getenv
        client_secret = None
        if getattr(p, 'client_secret_env', None):
            client_secret = getenv(p.client_secret_env)
        if getattr(p, 'secret_backend', None) and getattr(p, 'secret_ref', None) and not client_secret:
            sec = get_secret(SecretSpec(backend=p.secret_backend, ref=p.secret_ref))
            if sec:
                client_secret = sec
        provider = AzureADTokenProvider(
            tenant_id=p.tenant_id,
            client_id=p.client_id,
            scopes=[p.scope],
            client_secret=client_secret,
            use_device_code=(client_secret is None),
        )
        return provider.get_token
    raise typer.BadParameter("No PACX_ACCESS_TOKEN and no default profile configured.")


def _get_token_getter(ctx: typer.Context, *, required: bool = True):
    ctx.ensure_object(dict)
    token_getter = ctx.obj.get("token_getter") if ctx.obj else None
    if callable(token_getter):
        return token_getter

    if token_getter is None:
        try:
            token_getter = _resolve_token_getter()
        except typer.BadParameter:
            if not required:
                return None
            raise
        ctx.obj["token_getter"] = token_getter

    return token_getter


@app.callback()
def common(ctx: typer.Context):
    ctx.ensure_object(dict)
    ctx.obj.setdefault("token_getter", None)


# ---- Core: environments/apps/flows ----

@app.command("env")
@handle_cli_errors
def list_envs(
    ctx: typer.Context,
    api_version: str = typer.Option("2022-03-01-preview", help="Power Platform API version"),
):
    """List Power Platform environments."""
    token_getter = _get_token_getter(ctx)
    client = PowerPlatformClient(token_getter, api_version=api_version)
    envs = client.list_environments()
    for e in envs:
        print(f"[bold]{e.name or e.id}[/bold]  type={e.type}  location={e.location}")


@app.command("apps")
@handle_cli_errors
def list_apps(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
    top: int | None = typer.Option(None, help="$top"),
):
    token_getter = _get_token_getter(ctx)
    environment_id = resolve_environment_id(environment_id)
    client = PowerPlatformClient(token_getter)
    apps = client.list_apps(environment_id, top=top)
    for a in apps:
        print(f"[bold]{a.name or a.id}[/bold]")


@app.command("flows")
@handle_cli_errors
def list_flows(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
):
    token_getter = _get_token_getter(ctx)
    environment_id = resolve_environment_id(environment_id)
    client = PowerPlatformClient(token_getter)
    flows = client.list_cloud_flows(environment_id)
    for f in flows:
        print(f"[bold]{f.name or f.id}[/bold]")


# ---- Solutions ----

@app.command("solution")
@handle_cli_errors
def solution_cmd(
    ctx: typer.Context,
    action: str = typer.Argument(..., help="list|export|import|publish-all|pack|unpack|unpack-sp|pack-sp"),
    host: str | None = typer.Option(None, help="Dataverse host (e.g. org.crm.dynamics.com)"),
    name: str | None = typer.Option(None, help="Solution unique name (for export)"),
    managed: bool = typer.Option(False, help="Export as managed"),
    file: str | None = typer.Option(None, help="Path to solution zip (import/export/pack)"),
    src: str | None = typer.Option(None, help="Folder to pack from (pack)"),
    out: str | None = typer.Option(None, help="Output path (export/pack/unpack)"),
    wait: bool = typer.Option(False, help="Wait for long-running operations (import)"),
    import_job_id: str | None = typer.Option(None, help="Provide/track ImportJobId for import"),
):
    from .solution_source import pack_solution_folder, unpack_solution_zip

    cfg = ConfigStore().load()
    requires_dataverse = action in ("list", "export", "import", "publish-all")
    resolved_host = resolve_dataverse_host(host, config=cfg) if requires_dataverse else None
    token_getter = _get_token_getter(ctx, required=requires_dataverse)
    if requires_dataverse:
        dv = DataverseClient(token_getter, host=resolved_host)
    else:
        dv = None

    if action == "list":
        sols = dv.list_solutions(select="uniquename,friendlyname,version")
        for s in sols:
            print(f"[bold]{s.uniquename}[/bold]  {s.friendlyname}  v{s.version}")
    elif action == "export":
        if not name:
            raise typer.BadParameter("--name is required for export")
        req = ExportSolutionRequest(SolutionName=name, Managed=managed)
        data = dv.export_solution(req)
        outp = out or file or f"{name}.zip"
        with open(outp, "wb") as f:
            f.write(data)
        print(f"Exported to {outp}")
    elif action == "import":
        if not file:
            raise typer.BadParameter("--file is required for import")
        with open(file, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        job_id = import_job_id or __import__('uuid').uuid4().hex
        req = ImportSolutionRequest(CustomizationFile=b64, ImportJobId=job_id)
        dv.import_solution(req)
        print(f"Import submitted (job: {job_id})")
        if wait:
            status = dv.wait_for_import_job(job_id, interval=1.0, timeout=600.0)
            print(status)
    elif action == "unpack-sp":
        if not file:
            raise typer.BadParameter("--file required for unpack-sp")
        outp = out or "solution_src"
        unpack_to_source(file, outp)
        print(f"Unpacked (SolutionPackager-like) {file} -> {outp}")
    elif action == "pack-sp":
        if not src:
            raise typer.BadParameter("--src required for pack-sp")
        outp = out or file or "solution.zip"
        pack_from_source(src, outp)
        print(f"Packed (SolutionPackager-like) {src} -> {outp}")
    elif action == "publish-all":
        dv.publish_all()
        print("Published all customizations")
    elif action == "pack":
        if not src:
            raise typer.BadParameter("--src required for pack")
        outp = out or file or "solution.zip"
        pack_solution_folder(src, outp)
        print(f"Packed {src} -> {outp}")
    elif action == "unpack":
        if not file:
            raise typer.BadParameter("--file required for unpack")
        outp = out or "solution_unpacked"
        unpack_solution_zip(file, outp)
        print(f"Unpacked {file} -> {outp}")
    else:
        raise typer.BadParameter("Unknown action")


# ---- AUTH & PROFILES ----

@auth_app.command("device")
@handle_cli_errors
def auth_device(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    scope: str = typer.Option("https://api.powerplatform.com/.default", help="Scope (default: PP API)"),
    dataverse_host: str | None = typer.Option(None, help="Default DV host for this profile"),
):
    """Create/update a device-code profile. Token acquisition happens on use."""
    store = ConfigStore()
    p = Profile(name=name, tenant_id=tenant_id, client_id=client_id, scope=scope, dataverse_host=dataverse_host)
    store.add_or_update_profile(p)
    store.set_default_profile(name)
    print(f"Profile [bold]{name}[/bold] configured. It will use device code on demand.")


@auth_app.command("client")
@handle_cli_errors
def auth_client(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    client_secret_env: str | None = typer.Option(None, help="Name of env var holding the client secret (env backend)"),
    secret_backend: str | None = typer.Option(None, help="Secret backend: env|keyring|keyvault"),
    secret_ref: str | None = typer.Option(None, help="Backend ref: ENV_VAR or service:username or VAULT_URL:SECRET"),
    prompt_secret: bool = typer.Option(False, help="For keyring: prompt and store a secret under service:username"),
    scope: str = typer.Option("https://api.powerplatform.com/.default", help="Scope (default: PP API)"),
    dataverse_host: str | None = typer.Option(None, help="Default DV host for this profile"),
):
    """Create/update a client-credentials profile (secret read from env var on use)."""
    store = ConfigStore()
    p = Profile(name=name, tenant_id=tenant_id, client_id=client_id, scope=scope, dataverse_host=dataverse_host, client_secret_env=client_secret_env)
    # persist secret backend settings
    backend = secret_backend
    if backend:
        p.secret_backend = backend
        if secret_ref:
            p.secret_ref = secret_ref
        if backend == KEYRING_BACKEND and prompt_secret:
            try:
                import keyring
                if not secret_ref or ':' not in secret_ref:
                    raise typer.BadParameter("--secret-ref must be 'SERVICE:USERNAME' for keyring")
                service, username = secret_ref.split(':', 1)
                value = typer.prompt(f"Enter secret for {service}:{username}", hide_input=True)
                keyring.set_password(service, username, value)
                print("Stored secret in keyring.")
            except Exception as e:
                print(f"[yellow]Keyring not available or failed: {e}[/yellow]")
        if backend == KEYVAULT_BACKEND and not secret_ref:
            print("[yellow]Provide --secret-ref 'VAULT_URL:SECRET_NAME' for Key Vault[/yellow]")
    store.add_or_update_profile(p)
    store.set_default_profile(name)
    where = backend or ('env' if client_secret_env else 'device')
    print(f"Client-credentials profile [bold]{name}[/bold] configured. Backend: {where}")


@auth_app.command("use")
@handle_cli_errors
def auth_use(name: str = typer.Argument(..., help="Profile to activate")):
    store = ConfigStore()
    store.set_default_profile(name)
    print(f"Default profile set to [bold]{name}[/bold]")


@profile_app.command("list")
@handle_cli_errors
def profile_list():
    store = ConfigStore()
    cfg = store.load()
    names = sorted(list(cfg.profiles.keys())) if cfg.profiles else []
    for n in names:
        star = "*" if cfg.default_profile == n else " "
        print(f"{star} {n}")


@profile_app.command("show")
@handle_cli_errors
def profile_show(name: str = typer.Argument(..., help="Profile name")):
    store = ConfigStore()
    cfg = store.load()
    p = cfg.profiles.get(name) if cfg.profiles else None
    if not p:
        raise typer.BadParameter(f"Profile '{name}' not found")
    print(p.__dict__)


@profile_app.command("set-env")
@handle_cli_errors
def profile_set_env(environment_id: str = typer.Argument(..., help="Default Environment ID")):
    store = ConfigStore()
    cfg = store.load()
    cfg.environment_id = environment_id
    store.save(cfg)
    print(f"Default environment set to {environment_id}")


@profile_app.command("set-host")
@handle_cli_errors
def profile_set_host(dataverse_host: str = typer.Argument(..., help="Default Dataverse host")):
    store = ConfigStore()
    cfg = store.load()
    cfg.dataverse_host = dataverse_host
    store.save(cfg)
    print(f"Default Dataverse host set to {dataverse_host}")


# ---- Dataverse group ----

@dv_app.command("whoami")
@handle_cli_errors
def dv_whoami(ctx: typer.Context, host: str | None = typer.Option(None, help="Dataverse host (else config/env)")):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    print(dv.whoami())


@dv_app.command("list")
@handle_cli_errors
def dv_list(ctx: typer.Context, entityset: str = typer.Argument(...), select: str | None = None, filter: str | None = None, top: int | None = None, orderby: str | None = None, host: str | None = None):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    print(dv.list_records(entityset, select=select, filter=filter, top=top, orderby=orderby))


@dv_app.command("get")
@handle_cli_errors
def dv_get(ctx: typer.Context, entityset: str = typer.Argument(...), record_id: str = typer.Argument(...), host: str | None = None):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    print(dv.get_record(entityset, record_id))


@dv_app.command("create")
@handle_cli_errors
def dv_create(ctx: typer.Context, entityset: str = typer.Argument(...), data: str = typer.Option(..., help="JSON object string"), host: str | None = None):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    obj = json.loads(data)
    print(dv.create_record(entityset, obj))


@dv_app.command("update")
@handle_cli_errors
def dv_update(ctx: typer.Context, entityset: str = typer.Argument(...), record_id: str = typer.Argument(...), data: str = typer.Option(..., help="JSON object string"), host: str | None = None):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    obj = json.loads(data)
    dv.update_record(entityset, record_id, obj)
    print("updated")


@dv_app.command("delete")
@handle_cli_errors
def dv_delete(ctx: typer.Context, entityset: str = typer.Argument(...), record_id: str = typer.Argument(...), host: str | None = None):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    dv.delete_record(entityset, record_id)
    print("deleted")


# ---- Connectors ----

@connector_app.command("list")
@handle_cli_errors
def connectors_list(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
    top: int | None = typer.Option(None, help="$top"),
):
    token_getter = _get_token_getter(ctx)
    environment_id = resolve_environment_id(environment_id)
    c = ConnectorsClient(token_getter)
    data = c.list_apis(environment_id, top=top)
    for item in (data.get("value") or []):
        name = item.get("name") or item.get("id")
        print(f"[bold]{name}[/bold]")


@connector_app.command("get")
@handle_cli_errors
def connectors_get(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
    api_name: str = typer.Argument(..., help="API (connector) name"),
):
    token_getter = _get_token_getter(ctx)
    environment_id = resolve_environment_id(environment_id)
    c = ConnectorsClient(token_getter)
    data = c.get_api(environment_id, api_name)
    print(data)


@connector_app.command("push")
@handle_cli_errors
def connector_push(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(None, help="Environment ID (else from config)"),
    name: str = typer.Option(..., "--name", help="Connector name"),
    openapi_path: str = typer.Option(..., "--openapi", help="Path to OpenAPI/Swagger file (YAML/JSON)"),
    display_name: str | None = typer.Option(None, help="Display name override"),
):
    token_getter = _get_token_getter(ctx)
    environment_id = resolve_environment_id(environment_id)
    with open(openapi_path, encoding="utf-8") as f:
        text = f.read()
    c = ConnectorsClient(token_getter)
    out = c.put_api_from_openapi(environment_id, name, text, display_name=display_name)
    print(out)


@pages_app.command("download")
@handle_cli_errors
def pages_download(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option("core", help="Which tables: core|full|csv list of entity names"),
    binaries: bool = typer.Option(False, help="Use default binary provider (annotations)"),
    out: str = typer.Option("site_out", help="Output directory"),
    host: str | None = typer.Option(None, help="Dataverse host (else config/env)"),
    include_files: bool = typer.Option(True, help="Include adx_webfiles"),
    binary_provider: list[str] | None = BINARY_PROVIDER_OPTION,
    provider_options: str | None = typer.Option(None, help="JSON string/path for provider options"),
):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    if binary_provider and not include_files:
        raise typer.BadParameter("Binary providers require --include-files True")
    provider_opts: dict[str, dict[str, object]] = {}
    if provider_options:
        try:
            path = Path(provider_options)
            if path.exists():
                provider_opts = json.loads(path.read_text(encoding="utf-8"))
            else:
                provider_opts = json.loads(provider_options)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON for --provider-options: {exc}") from exc
    dv = DataverseClient(token_getter, host=resolved_host)
    pp = PowerPagesClient(dv)
    providers = list(binary_provider) if binary_provider else None
    res = pp.download_site(
        website_id,
        out,
        tables=tables,
        include_files=include_files,
        binaries=binaries,
        binary_providers=providers,
        provider_options=provider_opts,
    )
    print(f"Downloaded site to {res.output_path}")
    if res.providers:
        for name, prov in res.providers.items():
            print(f"Provider {name}: {len(prov.files)} files, skipped={prov.skipped}")


@pages_app.command("upload")
@handle_cli_errors
def pages_upload(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option("core", help="Which tables: core|full|csv list of entity names"),
    src: str = typer.Option(..., help="Source directory created by pages download"),
    host: str | None = typer.Option(None, help="Dataverse host (else config/env)"),
    strategy: str = typer.Option("replace", help="replace|merge|skip-existing|create-only"),
    key_config: str | None = typer.Option(None, help="JSON string/path overriding natural keys"),
):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    pp = PowerPagesClient(dv)
    manifest_path = Path(src) / "manifest.json"
    manifest_keys: dict[str, list[str]] = {}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_keys = {k: list(v) for k, v in data.get("natural_keys", {}).items()}
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.debug("Failed to load manifest keys from %s: %s", manifest_path, exc)
    cli_keys: dict[str, list[str]] = {}
    if key_config:
        try:
            path = Path(key_config)
            if path.exists():
                cli_keys = json.loads(path.read_text(encoding="utf-8"))
            else:
                cli_keys = json.loads(key_config)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON for --key-config: {exc}") from exc
    key_map = manifest_keys
    key_map.update(cli_keys)
    pp.upload_site(website_id, src, tables=tables, strategy=strategy, key_config=key_map)
    print("Uploaded site content")


@pages_app.command("diff-permissions")
@handle_cli_errors
def pages_diff_permissions(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID"),
    src: str = typer.Option(..., help="Local export directory"),
    host: str | None = typer.Option(None, help="Dataverse host"),
    key_config: str | None = typer.Option(None, help="JSON string/path overriding keys"),
):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    manifest_path = Path(src) / "manifest.json"
    manifest_keys: dict[str, list[str]] = {}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_keys = {k: list(v) for k, v in data.get("natural_keys", {}).items()}
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.debug("Failed to load manifest keys from %s: %s", manifest_path, exc)
    cli_keys: dict[str, list[str]] = {}
    if key_config:
        try:
            path = Path(key_config)
            if path.exists():
                cli_keys = json.loads(path.read_text(encoding="utf-8"))
            else:
                cli_keys = json.loads(key_config)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid JSON for --key-config: {exc}") from exc
    merged_keys = manifest_keys
    merged_keys.update(cli_keys)
    plan = diff_permissions(dv, website_id, src, key_config=merged_keys)
    if not plan:
        print("No permission differences detected.")
        return
    print("Permission diff plan:")
    for entry in plan:
        key_repr = ",".join(entry.key)
        print(f"- {entry.entityset}: {entry.action} [{key_repr}]")

@dv_app.command("bulk-csv")
@handle_cli_errors
def dv_bulk_csv(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    csv_path: str = typer.Argument(...),
    id_column: str = typer.Option(..., help="Column containing record id for PATCH; blank -> POST"),
    key_columns: str = typer.Option("", help="Comma-separated alternate key columns for PATCH when id is blank"),
    create_if_missing: bool = typer.Option(True, help="POST when id and key columns are not present"),
    host: str | None = None,
    chunk_size: int = typer.Option(50, help="Records per $batch"),
    report: str | None = typer.Option(None, help="Write per-op results CSV to this path"),
):
    token_getter = _get_token_getter(ctx)
    cfg = ConfigStore().load()
    resolved_host = resolve_dataverse_host(host, config=cfg)
    dv = DataverseClient(token_getter, host=resolved_host)
    keys = [s.strip() for s in (key_columns or '').split(',') if s.strip()]
    res = bulk_csv_upsert(
        dv,
        entityset,
        csv_path,
        id_column,
        key_columns=keys or None,
        chunk_size=chunk_size,
        create_if_missing=create_if_missing,
    )
    if report:
        import csv as _csv
        with open(report, 'w', newline='', encoding='utf-8') as f:
            w = _csv.writer(f)
            w.writerow(['row_index','content_id','status_code','reason','json'])
            for r in res.operations:
                w.writerow([r.get('row_index'), r.get('content_id'), r.get('status_code'), r.get('reason'), (r.get('json') or '')])
        print(f"Wrote per-op report to {report}")
    stats = res.stats
    print(
        "Bulk upsert completed: "
        f"{stats['successes']} succeeded, {stats['failures']} failed, "
        f"retries={stats['retry_invocations']}"
    )
