# Typing Audit for Optional Dependencies

The following third-party integrations used across `src/` and `tests/` either
lack bundled type information or are optional dependencies that may be absent at
runtime. They are now covered by stub packages or local shims to keep mypy
happy without relying on ``type: ignore`` comments.

| Module | Usage | Typing Strategy |
| --- | --- | --- |
| `cryptography.fernet` | Config encryption helpers in `src/pacx/config.py` and test fixtures | Added `types-cryptography` stub dependency and a runtime-safe protocol fallback. |
| `respx` | HTTP mocking fixtures under `tests/` | Added lightweight protocol stubs under `stubs/respx` and pointed mypy at them. |
| `keyring` | Secret retrieval helper in `src/pacx/secrets.py` | Introduced protocol-based loader to avoid importing when unavailable. |
| `azure.identity` / `azure.keyvault.secrets` | Azure Key Vault secret resolution in `src/pacx/secrets.py` | Added protocol-based loaders that expose minimal typed APIs when packages are missing. |
| `msal` | Azure AD token acquisition in `src/pacx/auth/azure_ad.py` | Added a typed loader using protocols for the client factories. |

These changes remove the remaining `type: ignore` directives that previously
masked missing stub warnings while keeping the optional dependency loading
logic unchanged.
