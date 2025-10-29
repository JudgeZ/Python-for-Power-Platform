# Project Plan

## What I Scanned
- Plans: `PLAN.md`, `plan.md`, `docs/plan.md`
- Docs: `docs/user-manual/02-authentication.md`, `docs/user-manual/03-cli-usage.md`
- Key modules: `src/pacx/auth/azure_ad.py`, `src/pacx/config.py`, `src/pacx/cli/auth.py`, `src/pacx/cli/common.py`, `src/pacx/secrets.py`, `src/pacx/cli/profile.py`
- Tests: `tests/auth/test_azure_oauth.py`, `tests/cli/test_auth_create.py`, `tests/cli/test_auth_aliases.py`, `tests/cli/test_token_resolution.py`, `tests/test_cli_common.py`, `tests/config/test_config_store.py`, `tests/secrets/test_keyring_refs.py`, `tests/cli/test_profile_masking.py`

## Status vs PLAN.md
- P0.1 Profiles + refresh caching: DONE (encryption + keyring-first, masking). `src/pacx/config.py`, `src/pacx/cli/profile.py`; tests: `tests/config/test_config_store.py`, `tests/cli/test_profile_masking.py`
- P0.2 Azure AD provider (refresh → device/web, client creds unchanged): DONE. `src/pacx/auth/azure_ad.py`; tests: `tests/auth/test_azure_oauth.py`
- P0.3 Unified CLI `ppx auth create` + aliases: DONE. `src/pacx/cli/auth.py`; tests: `tests/cli/test_auth_create.py`, `tests/cli/test_auth_aliases.py`
- P0.4 Token resolution precedence: DONE. `src/pacx/cli/common.py`; tests: `tests/cli/test_token_resolution.py`, `tests/test_cli_common.py`
- P0.5 Keyring-first refresh storage: DONE. `src/pacx/config.py`, `src/pacx/secrets.py`; tests: `tests/secrets/test_keyring_refs.py`, `tests/config/test_config_store.py`

- P1.1 set_secret helper: DONE. `src/pacx/secrets.py`; tests: `tests/secrets/test_set_secret.py`

- P1.2 documentation expansion: DONE. `docs/user-manual/02-authentication.md`, `docs/user-manual/03-cli-usage.md`

- P1.4 headless & CI guidance: DONE. `docs/user-manual/04-ci-examples.md`; tests: `tests/cli/test_ci_examples.py`

- P2.1 alias `ppx login`: DONE. `src/pacx/cli/__init__.py`; tests: `tests/cli/test_login_alias.py`
- P2.2 packaging extras: DONE. `pyproject.toml`; docs: `docs/user-manual/01-installation.md`
- P2.3 quickstart samples: DONE. `docs/examples/quickstart.py`, `docs/examples/quickstart.ipynb`
- Version bump: 0.6.1; `CHANGELOG.md` updated.
