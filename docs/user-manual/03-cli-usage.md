
# CLI Usage

The PACX command line interface is exposed through the `ppx` executable. Commands are grouped by workload so that you can quickly jump between authentication, Dataverse, Power Pages, or solution lifecycle tasks.

Need a guided tour? Walk through the [end-to-end quick start](01-installation.md#end-to-end-quick-start-scenario) before diving into individual command groups.

## Command groups at a glance

| Group | Description | Example |
| --- | --- | --- |
| `auth` | Configure and activate profiles used for authentication. | `ppx auth create my-profile --tenant-id ... --client-id ...` |
| `profile` | Inspect or change stored defaults such as the active environment or Dataverse host. | `ppx profile list` |
| `dv` | Dataverse data access helpers (whoami, CRUD, bulk CSV). | `ppx dv list accounts --top 5` |
| `connector` | Manage custom connector APIs within an environment. | `ppx connector list --environment-id ENV-ID` |
| `policy` | Administer Data Loss Prevention (DLP) policies and assignments. | `ppx policy dlp list` |
| `pages` | Download, upload, and diff Power Pages site content. | `ppx pages download --website-id <GUID>` |
| `solution` | Perform solution lifecycle operations (list, export/import, pack/unpack). | `ppx solution export --name core --out core.zip` |
| `env`/`apps`/`flows` | List environments, canvas apps, and cloud flows. | `ppx apps --environment-id ENV-ID` |
| `doctor` | Run environment diagnostics including token acquisition. | `ppx doctor` |
| `tenant` | Inspect and update tenant-level toggles and feature flights. | `ppx tenant settings get` |

Run `ppx --help` to see all registered groups and global options.

> **Note:** Legacy invocations such as `ppx solution --action list` (or positional `ppx solution list`)
> still forward to the matching subcommand, but the CLI now emits a one-time deprecation warning.
> Update automation to call explicit subcommands (`ppx solution <command>`) to avoid the shim.

## Common flags and defaults

PACX reads defaults from the active profile (set via `ppx auth use`) and the persisted configuration (`ppx profile set-env`, `ppx profile set-host`). Every command also accepts overrides:

- `--environment-id`: Overrides the environment configured on the profile. Useful when targeting another environment for connectors, apps, or flows.
- `--host`: Overrides the Dataverse host. When omitted, the CLI falls back to the profile setting or the `DATAVERSE_HOST` environment variable. You can supply either a bare hostname (`org.crm.dynamics.com`) or a full URL with scheme (`https://org.crm.dynamics.com`).
- `--top`: Many list commands expose the OData `$top` parameter to limit returned records; leaving it blank uses the server default (typically 100).
- `--select`, `--filter`, `--orderby`: Dataverse list commands accept the corresponding OData query parameters to shape the result set.

All commands support `--help`, which prints the description and option defaults drawn from the CLI docstrings. The regression tests in this repository verify that the help output stays informative.

## Token resolution order

Every CLI command eventually calls into the shared token resolver. The resolver walks multiple credential sources so that you can override cached values when needed:

1. `PACX_ACCESS_TOKEN` — an explicit environment override always wins.
2. Keyring or secret-store pointers (`token_backend` + `token_ref`) on the active profile.
3. The encrypted config file (`~/.pacx/config.json`) when `PACX_CONFIG_ENCRYPTION_KEY` is configured.
4. An interactive/refresh request via the Azure AD provider (device code, interactive browser, or client credentials).

The final step persists refreshed tokens back to the profile so future commands can reuse them.

## Example workflows

### Authenticate with device code

```shell
$ ppx auth create demo --tenant-id 00000000-0000-0000-0000-000000000000 --client-id 11111111-1111-1111-1111-111111111111 --flow device
Profile demo configured and set as the default profile.
Profile demo ready for device code flow.
```

After running the command, set the newly created profile as default:

```shell
$ ppx auth use demo
Default profile set to demo
```

### Explore Dataverse data

```shell
$ ppx dv list accounts --select name,accountnumber --top 3
{'value': [{'name': 'Fourth Coffee', 'accountnumber': 'ACC-001'}, ...]}
```

If you need to change tenants, provide a different host:

```shell
$ ppx dv whoami --host otherorg.crm.dynamics.com
{'UserId': '00000000-0000-0000-0000-000000000000'}
```

### Deploy a custom connector

```shell
$ ppx connector push --environment-id Default-123 --name sample-api --openapi openapi.yaml
{'name': 'sample-api'}
```

The command uploads the OpenAPI document and surfaces the connector name on success.

When you need to retire a connector, run `ppx connector delete` (optionally with
`--yes` for unattended scripts). The confirmation flow and exit codes are
documented in [Custom Connectors](./06-connectors.md#delete-a-connector).

### Manage solutions

```shell
$ ppx solution export --name contoso_solution --managed --out dist/contoso_solution_managed.zip
Exported to dist/contoso_solution_managed.zip
```

During imports you can add `--wait` to poll the import job until completion:

```shell
$ ppx solution import --file dist/contoso_solution_managed.zip --wait
Import submitted (job: 22222222222222222222222222222222)
{'state': 'Completed'}
```

### Administer Data Loss Prevention policies

```shell
$ ppx policy dlp list
Policy One  id=policy-1  state=Active  scope=Tenant
```

Create or update policies by supplying a JSON payload that mirrors the REST schema (at minimum `displayName` and `state`):

```shell
$ ppx policy dlp create --payload '{"displayName": "Finance", "state": "Draft"}' --wait
Policy creation completed status=Succeeded
{
  "operationId": "...",
  "status": "Succeeded"
}
```

When modifying connectors or assignments, provide the `groups` or `assignments` arrays exactly as documented in
`openapi/policy-datalossprevention.yaml`. Each command validates required scopes, so configure the active profile with
`Policy.DataLossPrevention.Read` for read-only commands and `Policy.DataLossPrevention.Manage` when performing updates.

### Round-trip Power Pages content

```shell
$ ppx pages download --website-id 33333333-3333-3333-3333-333333333333 --out site_out
Downloaded site to site_out
```

After updating the files locally, push the changes back:

```shell
$ ppx pages upload --website-id 33333333-3333-3333-3333-333333333333 --src site_out --strategy merge
Uploaded site content
```

Finally, compare web role permissions before deployment:

```shell
$ ppx pages diff-permissions --website-id 33333333-3333-3333-3333-333333333333 --src site_out
Permission diff plan:
- adx_webrole: add [roleid]
```

## Diagnostics

When commands fail unexpectedly, rerun them with `PACX_DEBUG=1` to surface stack traces. You can also validate the full setup using:

```shell
$ ppx doctor
[green]Token acquisition successful.[/green]
```

`ppx doctor` exits with a non-zero status code if Dataverse connectivity fails, making it suitable for CI smoke tests.

### Manage tenant settings and feature controls

Tenant-wide toggles are exposed through the `tenant` command group. Inspect the current configuration with:

```shell
$ ppx tenant settings get
```

Update operations (for both settings and features) require the `TenantSettings.Manage` scope or equivalent administrator privileges. The CLI surfaces asynchronous responses when the service accepts a change for background processing—pass `--async` to request `Prefer: respond-async` and capture the operation handle from the output.

Request elevated access when you do not currently hold the permission:

```shell
$ ppx tenant settings request-access --justification "Enable managed environments" --setting managedEnvironment
Tenant settings access request submitted.
```
