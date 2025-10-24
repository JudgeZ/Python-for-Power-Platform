# Installation & Quick Start

Use a virtual environment to isolate dependencies and install PACX in editable mode so that the CLI reflects any local changes immediately.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev,auth]     # add [secrets],[keyvault],[docs] as needed
pre-commit install
```

> **Tip:** The optional extras install MSAL authentication helpers (`auth`), keyring/Key Vault integrations (`secrets`, `keyvault`), and documentation tooling (`docs`). Add the ones you need to the install command up front.

## Quick start workflow

Follow the sequence below to bootstrap a profile, sign in, and run your first Dataverse command.

### 1. Create a profile shell

Profiles capture your tenant defaults and live under `~/.pacx/config.json` (override with `PACX_HOME`). Environment and host settings are global defaults—`ppx` does not scope them per profile—so configure them first and then create or use your profile.

```shell
$ ppx profile set-env Default-12345678-0000-0000-0000-000000000000
Environment set.
```

If your Dataverse host is different from the default, persist it as well:

```shell
$ ppx profile set-host org.crm.dynamics.com
Host set.
```

Run `ppx profile show` at any time to review the active defaults and existing profiles.

### 2. Authenticate with device code

Use device code flow when an interactive user can complete sign in via https://microsoft.com/devicelogin:

```shell
$ ppx auth device demo --tenant-id 00000000-0000-0000-0000-000000000000 --client-id 11111111-1111-1111-1111-111111111111
Open https://microsoft.com/devicelogin and enter ABCD-EFGH to authenticate.
Profile demo configured. It will use device code on demand.
```

Once the device challenge completes, make the profile active:

```shell
$ ppx auth use demo
Default profile set to demo.
```

### 3. Authenticate with a client secret (automation)

Headless jobs can rely on client credentials with an application secret stored in an environment variable, keyring, or Azure Key Vault. The example below uses an environment variable called `PACX__CLIENT_SECRET`:

```shell
$ export PACX__CLIENT_SECRET="super-secret-value"
$ ppx auth client automation --tenant-id 00000000-0000-0000-0000-000000000000 --client-id 22222222-2222-2222-2222-222222222222 \
    --secret-backend env --secret-ref PACX__CLIENT_SECRET
Profile automation configured for client credentials.
```

Switch between interactive and automation profiles at any time with `ppx auth use <profile>`.

### 4. Run basic commands

With authentication in place, verify connectivity and list some Dataverse data:

```shell
$ ppx dv whoami
{"UserId": "00000000-0000-0000-0000-000000000000"}

$ ppx dv list accounts --select name,accountnumber --top 3
{"value": [
  {"name": "Fourth Coffee", "accountnumber": "ACC-001"},
  {"name": "Adventure Works", "accountnumber": "ACC-002"},
  {"name": "Litware", "accountnumber": "ACC-003"}
]}
```

When you need richer diagnostics, run `ppx doctor` to check both authentication and Dataverse access.

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
