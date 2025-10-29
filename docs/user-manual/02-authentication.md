
# Authentication

- **Device code**: `ppx auth create ... --flow device`
- **Interactive browser**: `ppx auth create ... --flow web`
- **Client credentials**: `ppx auth create ... --flow client-credential`
- **Secret backends**: env, keyring, Key Vault (see flags for `ppx auth create --flow client-credential`).

## Profiles and masking

- Create multiple profiles to target different tenants or apps; switch with `ppx auth use <name>`.
- Tokens are stored securely. The CLI prefers the system keyring when available; otherwise it uses the encrypted config (set `PACX_CONFIG_ENCRYPTION_KEY`).
- Sensitive values (access/refresh tokens) are masked in CLI output.

## Token order (summary)

When a command needs a token, PACX resolves it in this order:
1) `PACX_ACCESS_TOKEN` env → 2) profile `token_backend`/`token_ref` (e.g., keyring) → 3) encrypted config → 4) provider refresh/interactive (device, web, or client credentials). Refreshed tokens are persisted back to the profile.

See also: CLI details in 03-cli-usage.md (Token resolution order).

## Choose a flow

### Device Code
- Best for terminals, SSH, and headless shells.
- Prints a verification URL and short code; approve in a browser.
- Works even when local browser SSO is constrained.

### Web
- Best for local development with a browser.
- Opens an interactive sign-in and consent screen.
- Use when admin/user consent must be granted interactively.

### Client Credentials
- Best for automation with a service principal (no user).
- Requires app permissions and a secret or certificate.
- No user refresh token; ensure scopes allow app-only access.

## Troubleshooting

- AAD consent required (e.g., `AADSTS65001`): use `--flow web` to grant consent, or have an admin pre‑consent for the tenant.
- Tenant mismatch (account not found/unauthorized): ensure `--tenant-id` matches the target tenant; switch with `ppx auth use <name>` and verify with `ppx dv whoami`.
- Missing keyring backend: `pip install keyring`. In CI/headless, PACX falls back to encrypted config; you may also use a non‑keyring backend via `ppx auth create --help`.
