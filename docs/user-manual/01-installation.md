# Installation & Quick Start

Use a virtual environment to isolate dependencies and install PACX in editable mode so that the CLI reflects any local changes immediately.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev,auth]     # add [secrets],[keyvault],[docs] as needed
pre-commit install
```

> **Tip:** The optional extras install MSAL authentication helpers (`auth`), keyring/Key Vault integrations (`secrets`, `keyvault`), and documentation tooling (`docs`). Add the ones you need to the install command up front.

## End-to-end quick start scenario

Work through the following scenario to go from a clean checkout to pushing an update across Dataverse, custom connectors, solutions, and Power Pages. Each step assumes the previous one succeeded.

### 1. Prepare the workspace

Create and activate a virtual environment, install PACX with the authentication helpers, and verify that the CLI is on the `PATH`:

```shell
$ python -m venv .venv
$ . .venv/bin/activate
(.venv) $ pip install -e .[dev,auth]
Obtaining file:///workspace/Python-for-Power-Platform
...
Successfully installed pacx 0.0.0
(.venv) $ ppx --version
ppx, version 0.0.0
```

### 2. Configure profile defaults

Profiles capture reusable authentication context, while the Dataverse environment and host are stored as global defaults. Set the defaults once so every profile uses the same environment unless you override it with explicit flags:

```shell
(.venv) $ ppx profile set-env Default-12345678-0000-0000-0000-000000000000
Environment set.

(.venv) $ ppx profile set-host org.crm.dynamics.com
Host set.
```

Use `ppx profile show` to review stored profiles at any time.

### 3. Authenticate the primary profile

Run the device code flow to bootstrap a reusable profile named `demo` and mark it as active once the browser challenge finishes:

```shell
(.venv) $ ppx auth device demo \
    --tenant-id 00000000-0000-0000-0000-000000000000 \
    --client-id 11111111-1111-1111-1111-111111111111
Open https://microsoft.com/devicelogin and enter ABCD-EFGH to authenticate.
Profile demo configured. It will use device code on demand.

(.venv) $ ppx auth use demo
Default profile set to demo.
```

Need service principals or non-interactive automation? Continue to [Authentication](02-authentication.md#choose-your-flow) for client credentials, certificates, and secret storage guidance.

### 4. Validate Dataverse connectivity

Confirm token acquisition and list a few account records to make sure the environment defaults are wired correctly:

```shell
(.venv) $ ppx dv whoami
{"UserId": "00000000-0000-0000-0000-000000000000"}

(.venv) $ ppx dv list accounts --select name,accountnumber --top 3
{"value": [
  {"name": "Fourth Coffee", "accountnumber": "ACC-001"},
  {"name": "Adventure Works", "accountnumber": "ACC-002"},
  {"name": "Litware", "accountnumber": "ACC-003"}
]}
```

When you need richer diagnostics, run `ppx doctor` to check both authentication and Dataverse API access.

### 5. Publish an updated custom connector

Package updates with the same profile context to keep environments consistent:

```shell
(.venv) $ ppx connector push \
    --environment-id Default-12345678-0000-0000-0000-000000000000 \
    --name sample-api \
    --openapi connectors/sample-api.yaml
{"name": "sample-api", "displayName": "Sample API"}
```

The `connector push` command uploads the OpenAPI definition and immediately reports the connector metadata. For advanced operations—such as rotating policies or deleting unused connectors—head to [Custom Connectors](06-connectors.md).

### 6. Export a managed solution snapshot

With the same authenticated session, export a solution so that downstream environments can ingest the package:

```shell
(.venv) $ ppx solution export \
    --name contoso_core \
    --managed \
    --out dist/contoso_core_managed.zip
Exported to dist/contoso_core_managed.zip
```

Add `--wait` to `ppx solution import` to follow the job until it completes. See [Solution lifecycle](07-solutions.md) for packing, unpacking, and deployment automation patterns.

### 7. Round-trip Power Pages content

Finally, pull the latest portal assets, make a change, and push it back to Dataverse:

```shell
(.venv) $ ppx pages download \
    --website-id 33333333-3333-3333-3333-333333333333 \
    --out site_out
Downloaded site to site_out

(.venv) $ ppx pages upload \
    --website-id 33333333-3333-3333-3333-333333333333 \
    --src site_out \
    --strategy merge
Uploaded site content
```

Run `ppx pages diff-permissions` before deployment to spot role changes. Continue in [Power Pages](04-power-pages.md) for more automation-friendly workflows and content packaging tips.

## Troubleshooting

### Missing dependencies or `ppx` command not found

- Ensure the virtual environment is activated (`. .venv/bin/activate`) before invoking `ppx`.
- Re-run the editable install if new extras are required: `pip install -e .[auth,secrets,keyvault]`.
- If `msal` or `cryptography` import errors appear, install the `auth` extra and restart the command.

### Permission errors writing `~/.pacx/config.json`

- PACX locks configuration files to user-only access. On Unix-like systems, fix permissions with `chmod 600 ~/.pacx/config.json`.
- If the file is owned by another account (common after running with `sudo`), restore ownership: `chown $(whoami) ~/.pacx/config.json`.
- Override the config location when running in containers with restricted home directories: `export PACX_HOME=/workspace/.pacx` before calling the CLI.

Refer to the [Authentication guide](02-authentication.md) for advanced flows and secret management strategies.
