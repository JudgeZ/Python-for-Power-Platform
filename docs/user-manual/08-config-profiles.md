# Config & Profiles

- `ppx profile list|show|set-env|set-host`
- Profiles are stored under `~/.pacx/config.json` (override with `PACX_HOME`).

## Secure storage

PACX persists CLI state (default profile, Dataverse host, access tokens, etc.) in
`~/.pacx/config.json`. Recent releases automatically lock down the file so that
only the current user can read or write it. On Linux and macOS the file is
written with permissions `0600`. Windows uses the closest equivalent via
`os.chmod`.

If PACX detects a permissive mask (for example, `0664`) when loading the
configuration it will tighten the permissions and emit a warning. You can verify
the permissions manually:

```bash
ls -l ~/.pacx/config.json
# -rw-------  1 you  staff  ... config.json
```

### Optional encryption

To further harden access tokens, PACX can encrypt sensitive fields using
`cryptography.Fernet`. Encryption is enabled when the environment variable
`PACX_CONFIG_ENCRYPTION_KEY` is set. The value can be either a 32-byte
URL-safe base64 string or any passphrase—PACX will derive a valid key
automatically.

```bash
export PACX_CONFIG_ENCRYPTION_KEY="use-a-strong-passphrase"
ppx profile login
```

When the key is set, PACX encrypts the `access_token` field before writing to
disk. The token is transparently decrypted when loading the profile. If the file
contains encrypted data and the key is not supplied, PACX aborts with a helpful
error instead of returning garbage.

!!! note
    Keep the passphrase secret. Anyone with the same key can decrypt the stored
    access tokens.
