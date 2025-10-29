# CI Examples

Short, copy‑paste snippets for headless and semi‑headless auth in CI.

## Device Code

Device Code is non‑interactive for the job but requires an out‑of‑band browser approval. Use when a human can approve during the run.

```bash
# Set IDs from your CI secret store
export TENANT_ID="00000000-0000-0000-0000-000000000000"
export CLIENT_ID="11111111-1111-1111-1111-111111111111"

# Create a profile configured for device code
ppx auth create ci --tenant-id "$TENANT_ID" --client-id "$CLIENT_ID" --flow device

# Trigger the challenge and acquire a token (prints the URL + code)
ppx doctor
```

Notes
- Prefer storing refresh tokens in a local keyring; in CI use the platform’s secret store.
- CLI output masks sensitive values.

## Client Credentials

Fully headless with a service principal. Provide a secret via env or a secret backend.

```bash
export TENANT_ID="00000000-0000-0000-0000-000000000000"
export CLIENT_ID="22222222-2222-2222-2222-222222222222"
export SERVICE_SECRET="…"

ppx auth create ci-sp \
  --tenant-id "$TENANT_ID" \
  --client-id "$CLIENT_ID" \
  --flow client-credential \
  --client-secret-env SERVICE_SECRET
```

Or reference Key Vault / keyring for the secret using `--secret-backend` and `--secret-ref`.

## Secure storage

- Local: system keyring preferred; encrypted config is used when keyring is unavailable.
- CI: keep secrets in the pipeline secret store; avoid printing tokens in logs.
