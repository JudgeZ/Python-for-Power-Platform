
# ADR 0001 — Secrets Backends

**Status**: Accepted
**Context**: Need to support multiple ways to supply client secrets (env, keyring, Azure Key Vault).
**Decision**: Add `secret_backend` + `secret_ref` fields to profiles, with resolution after `PACX_ACCESS_TOKEN` and `client_secret_env`.
**Consequences**: Extra optional dependencies for keyring/Azure. Clear precedence order minimizes ambiguity.
