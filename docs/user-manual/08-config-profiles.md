# Config & Profiles

- `ppx profile list|show|set-env|set-host`
- Profiles are stored under `~/.pacx/config.json` (override with `PACX_HOME`).

## Secure storage

PACX automatically hardens `config.json` after every write:

- On Linux/macOS the file is saved with permissions `0600` (read/write for the
  current user only). If broader permissions are detected when the file is
  loaded, PACX resets them and logs a warning.
- On Windows the CLI makes a best-effort call to restrict access to the
  interactive user. If that is not possible, PACX emits a warning so you can
  adjust ACLs manually.

You can verify the permission mode at any time:

```bash
ls -l ~/.pacx/config.json
```

## Optional encryption

To protect access and refresh tokens at rest, PACX supports transparent field
encryption. Set `PACX_CONFIG_ENCRYPTION_KEY` before running the CLI; a new
config write will encrypt sensitive fields (currently access tokens) using
[Fernet](https://cryptography.io/en/latest/fernet/).

1. Generate a key (one-time) and store it securely:

    ```bash
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```

2. Export the key and run PACX as usual:

    ```bash
    export PACX_CONFIG_ENCRYPTION_KEY=your-generated-key
    ppx profile show default
    ```

When the key is set and `cryptography` is available, PACX encrypts tokens during
saves and decrypts them transparently when loading. If the key is missing when
an encrypted config is read, the CLI now emits recovery guidance:

1. Restore the original key (the one that was exported to
   `PACX_CONFIG_ENCRYPTION_KEY`) and re-run the command. The CLI will decrypt
   existing secrets automatically.
2. If the key is irretrievable, back up and remove the encrypted config file
   (`~/.pacx/config.json` unless `PACX_HOME` overrides it) and run
   `ppx auth create NAME --flow device` to bootstrap fresh credentials.
