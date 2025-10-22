
from __future__ import annotations

import base64
import json
import os
from typing import Optional

import typer
from rich import print

from .clients.power_platform import PowerPlatformClient
from .clients.dataverse import DataverseClient
from .clients.connectors import ConnectorsClient
from .clients.power_pages import PowerPagesClient
from .bulk_csv import bulk_csv_upsert
from .solution_sp import unpack_to_source, pack_from_source
from .models.dataverse import ExportSolutionRequest, ImportSolutionRequest
from .config import ConfigStore, Profile
from .secrets import SecretSpec, get_secret

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


@app.callback()
def common(ctx: typer.Context):
    ctx.obj = {"token_getter": _resolve_token_getter}


# ---- Core: environments/apps/flows ----

@app.command("env")
def list_envs(
    ctx: typer.Context,
    api_version: str = typer.Option("2022-03-01-preview", help="Power Platform API version"),
):
    """List Power Platform environments."""
    token_getter = ctx.obj["token_getter"]
    client = PowerPlatformClient(token_getter, api_version=api_version)
    envs = client.list_environments()
    for e in envs:
        print(f"[bold]{e.name or e.id}[/bold]  type={e.type}  location={e.location}")


@app.command("apps")
def list_apps(
    ctx: typer.Context,
    environment_id: Optional[str] = typer.Option(None, help="Environment ID (else from config)"),
    top: Optional[int] = typer.Option(None, help="$top"),
):
    token_getter = ctx.obj["token_getter"]
    if not environment_id:
        cfg = ConfigStore().load()
        environment_id = cfg.environment_id
    if not environment_id:
        raise typer.BadParameter("Missing --environment-id and no default in config.")
    client = PowerPlatformClient(token_getter)
    apps = client.list_apps(environment_id, top=top)
    for a in apps:
        print(f"[bold]{a.name or a.id}[/bold]")


@app.command("flows")
def list_flows(
    ctx: typer.Context,
    environment_id: Optional[str] = typer.Option(None, help="Environment ID (else from config)"),
):
    token_getter = ctx.obj["token_getter"]
    if not environment_id:
        cfg = ConfigStore().load()
        environment_id = cfg.environment_id
    if not environment_id:
        raise typer.BadParameter("Missing --environment-id and no default in config.")
    client = PowerPlatformClient(token_getter)
    flows = client.list_cloud_flows(environment_id)
    for f in flows:
        print(f"[bold]{f.name or f.id}[/bold]")


# ---- Solutions ----

@app.command("solution")
def solution_cmd(
    ctx: typer.Context,
    action: str = typer.Argument(..., help="list|export|import|publish-all|pack|unpack|unpack-sp|pack-sp"),
    host: Optional[str] = typer.Option(None, help="Dataverse host (e.g. org.crm.dynamics.com)"),
    name: Optional[str] = typer.Option(None, help="Solution unique name (for export)"),
    managed: bool = typer.Option(False, help="Export as managed"),
    file: Optional[str] = typer.Option(None, help="Path to solution zip (import/export/pack)"),
    src: Optional[str] = typer.Option(None, help="Folder to pack from (pack)"),
    out: Optional[str] = typer.Option(None, help="Output path (export/pack/unpack)"),
    wait: bool = typer.Option(False, help="Wait for long-running operations (import)"),
    import_job_id: Optional[str] = typer.Option(None, help="Provide/track ImportJobId for import"),
):
    from .solution_source import pack_solution_folder, unpack_solution_zip

    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host and action in ("list", "export", "import", "publish-all"):
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default dataverse_host")

    if action in ("list", "export", "import", "publish-all"):
        dv = DataverseClient(token_getter, host=host)

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
def auth_device(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    scope: str = typer.Option("https://api.powerplatform.com/.default", help="Scope (default: PP API)"),
    dataverse_host: Optional[str] = typer.Option(None, help="Default DV host for this profile"),
):
    """Create/update a device-code profile. Token acquisition happens on use."""
    store = ConfigStore()
    p = Profile(name=name, tenant_id=tenant_id, client_id=client_id, scope=scope, dataverse_host=dataverse_host)
    store.add_or_update_profile(p)
    store.set_default_profile(name)
    print(f"Profile [bold]{name}[/bold] configured. It will use device code on demand.")


@auth_app.command("client")
def auth_client(
    name: str = typer.Argument(..., help="Profile name"),
    tenant_id: str = typer.Option(..., help="Entra ID tenant"),
    client_id: str = typer.Option(..., help="App registration (client) ID"),
    client_secret_env: Optional[str] = typer.Option(None, help="Name of env var holding the client secret (env backend)"),
    secret_backend: Optional[str] = typer.Option(None, help="Secret backend: env|keyring|keyvault"),
    secret_ref: Optional[str] = typer.Option(None, help="Backend ref: ENV_VAR or service:username or VAULT_URL:SECRET"),
    prompt_secret: bool = typer.Option(False, help="For keyring: prompt and store a secret under service:username"),
    scope: str = typer.Option("https://api.powerplatform.com/.default", help="Scope (default: PP API)"),
    dataverse_host: Optional[str] = typer.Option(None, help="Default DV host for this profile"),
):
    """Create/update a client-credentials profile (secret read from env var on use)."""
    store = ConfigStore()
    p = Profile(name=name, tenant_id=tenant_id, client_id=client_id, scope=scope, dataverse_host=dataverse_host, client_secret_env=client_secret_env)
    # persist secret backend settings
    if secret_backend:
        p.secret_backend = secret_backend
        if secret_ref:
            p.secret_ref = secret_ref
        if secret_backend == 'keyring' and prompt_secret:
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
        if secret_backend == 'keyvault' and not secret_ref:
            print("[yellow]Provide --secret-ref 'VAULT_URL:SECRET_NAME' for Key Vault[/yellow]")
    store.add_or_update_profile(p)
    store.set_default_profile(name)
    where = secret_backend or ('env' if client_secret_env else 'device')
    print(f"Client-credentials profile [bold]{name}[/bold] configured. Backend: {where}")


@auth_app.command("use")
def auth_use(name: str = typer.Argument(..., help="Profile to activate")):
    store = ConfigStore()
    store.set_default_profile(name)
    print(f"Default profile set to [bold]{name}[/bold]")


@profile_app.command("list")
def profile_list():
    store = ConfigStore()
    cfg = store.load()
    names = sorted(list(cfg.profiles.keys())) if cfg.profiles else []
    for n in names:
        star = "*" if cfg.default_profile == n else " "
        print(f"{star} {n}")


@profile_app.command("show")
def profile_show(name: str = typer.Argument(..., help="Profile name")):
    store = ConfigStore()
    cfg = store.load()
    p = cfg.profiles.get(name) if cfg.profiles else None
    if not p:
        raise typer.BadParameter(f"Profile '{name}' not found")
    print(p.__dict__)


@profile_app.command("set-env")
def profile_set_env(environment_id: str = typer.Argument(..., help="Default Environment ID")):
    store = ConfigStore()
    cfg = store.load()
    cfg.environment_id = environment_id
    store.save(cfg)
    print(f"Default environment set to {environment_id}")


@profile_app.command("set-host")
def profile_set_host(dataverse_host: str = typer.Argument(..., help="Default Dataverse host")):
    store = ConfigStore()
    cfg = store.load()
    cfg.dataverse_host = dataverse_host
    store.save(cfg)
    print(f"Default Dataverse host set to {dataverse_host}")


# ---- Dataverse group ----

@dv_app.command("whoami")
def dv_whoami(ctx: typer.Context, host: Optional[str] = typer.Option(None, help="Dataverse host (else config/env)")):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    print(dv.whoami())


@dv_app.command("list")
def dv_list(ctx: typer.Context, entityset: str = typer.Argument(...), select: Optional[str] = None, filter: Optional[str] = None, top: Optional[int] = None, orderby: Optional[str] = None, host: Optional[str] = None):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    print(dv.list_records(entityset, select=select, filter=filter, top=top, orderby=orderby))


@dv_app.command("get")
def dv_get(ctx: typer.Context, entityset: str = typer.Argument(...), record_id: str = typer.Argument(...), host: Optional[str] = None):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    print(dv.get_record(entityset, record_id))


@dv_app.command("create")
def dv_create(ctx: typer.Context, entityset: str = typer.Argument(...), data: str = typer.Option(..., help="JSON object string"), host: Optional[str] = None):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    obj = json.loads(data)
    print(dv.create_record(entityset, obj))


@dv_app.command("update")
def dv_update(ctx: typer.Context, entityset: str = typer.Argument(...), record_id: str = typer.Argument(...), data: str = typer.Option(..., help="JSON object string"), host: Optional[str] = None):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    obj = json.loads(data)
    dv.update_record(entityset, record_id, obj)
    print("updated")


@dv_app.command("delete")
def dv_delete(ctx: typer.Context, entityset: str = typer.Argument(...), record_id: str = typer.Argument(...), host: Optional[str] = None):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    dv.delete_record(entityset, record_id)
    print("deleted")


# ---- Connectors ----

@connector_app.command("list")
def connectors_list(
    ctx: typer.Context,
    environment_id: Optional[str] = typer.Option(None, help="Environment ID (else from config)"),
    top: Optional[int] = typer.Option(None, help="$top"),
):
    token_getter = ctx.obj["token_getter"]
    if not environment_id:
        cfg = ConfigStore().load()
        environment_id = cfg.environment_id
    if not environment_id:
        raise typer.BadParameter("Missing --environment-id and no default in config.")
    c = ConnectorsClient(token_getter)
    data = c.list_apis(environment_id, top=top)
    for item in (data.get("value") or []):
        name = item.get("name") or item.get("id")
        print(f"[bold]{name}[/bold]")


@connector_app.command("get")
def connectors_get(
    ctx: typer.Context,
    environment_id: Optional[str] = typer.Option(None, help="Environment ID (else from config)"),
    api_name: str = typer.Argument(..., help="API (connector) name"),
):
    token_getter = ctx.obj["token_getter"]
    if not environment_id:
        cfg = ConfigStore().load()
        environment_id = cfg.environment_id
    if not environment_id:
        raise typer.BadParameter("Missing --environment-id and no default in config.")
    c = ConnectorsClient(token_getter)
    data = c.get_api(environment_id, api_name)
    print(data)


@connector_app.command("push")
def connector_push(
    ctx: typer.Context,
    environment_id: Optional[str] = typer.Option(None, help="Environment ID (else from config)"),
    name: str = typer.Option(..., "--name", help="Connector name"),
    openapi_path: str = typer.Option(..., "--openapi", help="Path to OpenAPI/Swagger file (YAML/JSON)"),
    display_name: Optional[str] = typer.Option(None, help="Display name override"),
):
    token_getter = ctx.obj["token_getter"]
    if not environment_id:
        cfg = ConfigStore().load()
        environment_id = cfg.environment_id
    if not environment_id:
        raise typer.BadParameter("Missing --environment-id and no default in config.")
    with open(openapi_path, "r", encoding="utf-8") as f:
        text = f.read()
    c = ConnectorsClient(token_getter)
    out = c.put_api_from_openapi(environment_id, name, text, display_name=display_name)
    print(out)


@pages_app.command("download")
def pages_download(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option("core", help="Which tables: core|full|csv list of entity names"),
    binaries: bool = typer.Option(False, help="Extract web file binaries to files_bin/"),
    out: str = typer.Option("site_out", help="Output directory"),
    host: Optional[str] = typer.Option(None, help="Dataverse host (else config/env)"),
    include_files: bool = typer.Option(True, help="Include adx_webfiles"),
):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    pp = PowerPagesClient(dv)
    outp = pp.download_site(website_id, out, tables=tables, include_files=include_files, binaries=binaries)
    print(f"Downloaded site to {outp}")


@pages_app.command("upload")
def pages_upload(
    ctx: typer.Context,
    website_id: str = typer.Option(..., help="adx_website id GUID (without braces)"),
    tables: str = typer.Option("core", help="Which tables: core|full|csv list of entity names"),
    binaries: bool = typer.Option(False, help="Extract web file binaries to files_bin/"),
    src: str = typer.Option(..., help="Source directory created by pages download"),
    host: Optional[str] = typer.Option(None, help="Dataverse host (else config/env)"),
):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    pp = PowerPagesClient(dv)
    pp.upload_site(website_id, src, strategy=merge_strategy)
    print("Uploaded site content")


@dv_app.command("bulk-csv")
def dv_bulk_csv(
    ctx: typer.Context,
    entityset: str = typer.Argument(...),
    csv_path: str = typer.Argument(...),
    id_column: str = typer.Option(..., help="Column containing record id for PATCH; blank -> POST"),
    key_columns: str = typer.Option("", help="Comma-separated alternate key columns for PATCH when id is blank"),
    create_if_missing: bool = typer.Option(True, help="POST when id and key columns are not present"),
    host: Optional[str] = None,
    chunk_size: int = typer.Option(50, help="Records per $batch"),
    report: Optional[str] = typer.Option(None, help="Write per-op results CSV to this path"),
):
    token_getter = ctx.obj["token_getter"]
    cfg = ConfigStore().load()
    host = host or os.getenv("DATAVERSE_HOST") or (cfg.dataverse_host if cfg else None)
    if not host:
        raise typer.BadParameter("Missing --host, DATAVERSE_HOST, or config default")
    dv = DataverseClient(token_getter, host=host)
    keys = [s.strip() for s in (key_columns or '').split(',') if s.strip()]
    res = bulk_csv_upsert(dv, entityset, csv_path, id_column, key_columns=keys or None, chunk_size=chunk_size, create_if_missing=create_if_missing)
    if report:
        import csv as _csv
        with open(report, 'w', newline='', encoding='utf-8') as f:
            w = _csv.writer(f)
            w.writerow(['row_index','content_id','status_code','reason','json'])
            for r in res:
                w.writerow([r.get('row_index'), r.get('content_id'), r.get('status_code'), r.get('reason'), (r.get('json') or '')])
        print(f"Wrote per-op report to {report}")
    print("Bulk upsert submitted via $batch")
