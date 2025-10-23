# Config Security

PACX persists CLI configuration under `~/.pacx/config.json` (or the path
defined by `PACX_HOME`). This file contains sensitive information such as OAuth
tokens and must be protected.

## File permissions

* PACX now enforces user-only permissions (read/write) on the configuration
  file. On Linux and macOS the file is written with `0600`. On Windows a best
  effort `chmod` call removes group/other access bits.
* If the CLI discovers that the file is more permissive (for example `0644`),
  it automatically corrects the permissions and emits a warning so you can
  investigate how the mode drifted.

These protections apply automatically; no manual action is needed beyond
ensuring your user account owns the directory.

## Optional token encryption

You can encrypt stored access tokens by providing a symmetric key via the
`PACX_CONFIG_ENCRYPTION_KEY` environment variable (Base64-encoded Fernet key).

```bash
export PACX_CONFIG_ENCRYPTION_KEY="$(python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
)"
```

When the key is present and the `cryptography` package is installed, PACX wraps
each token before persisting it. Tokens are decrypted on demand when you load a
profile. If no key is provided—or `cryptography` is unavailable—the CLI stores
tokens in plaintext and logs a debug message. All other profile metadata remains
unencrypted so that configuration diffs stay readable.

> **Tip:** Keep a secure backup of the encryption key. Without it the CLI cannot
> decrypt existing tokens, although the encrypted values remain in the config
> file so you can restore access later by re-setting the same key.

## Rotating the encryption key

1. Set `PACX_CONFIG_ENCRYPTION_KEY` to the new key.
2. Run any command that updates the profile (for example `ppx profile list`).
   PACX re-encrypts tokens using the new key the next time it writes the config.
3. Remove the old key from your environment and credential stores.

## Troubleshooting

* **Encryption key is invalid** — PACX logs a warning and continues in
  plaintext mode. Regenerate a valid Fernet key and set the environment variable
  again.
* **Encrypted token cannot be decrypted** — PACX ignores the value and prompts
  you to re-authenticate on the next command. This usually happens when the key
  changes or the config file is copied between machines without copying the key.
