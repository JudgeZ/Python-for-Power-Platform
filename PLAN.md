# PLAN.md — OAuth (like `pac` CLI) for Python-for-Power-Platform

This plan delivers **production-grade OAuth 2.0** for all Power Platform APIs (Dataverse Web API, Admin APIs, etc.), matching the `pac` CLI experience.
It includes **device code**, **authorization code (browser)**, and **client credentials** flows, plus **secure token caching**, **multi-profile** support, and **Codex-ready prompts**.

> **Repo paths** below assume a library layout like `src/pacx/...` and tests under `tests/...`. If your repo differs, adjust paths accordingly.

---

## Global conventions

- Keep **backward compatibility**; deprecate old commands but do not break them.
- Enforce: `ruff --fix .`, `black .`, `mypy .`, `pytest -q` must be green.
- Use existing error plumbing (`handle_cli_errors`) and **never print secrets**.
- Prefer `HttpClient` abstraction for HTTP operations; avoid direct `httpx` usage unless routed through the shared client.
- Store tokens **in keyring** when available; otherwise in **encrypted config** (already supported).
- Each task updates **docs** and adds **tests**. Use **Conventional Commits**.
- Ensure new behaviors ship with changelog updates and ADR references where the design deviates from the current architecture.

---

# P0 — Core OAuth enablement

## P0.1 Profiles: provider & refresh token
**Goal**: Profiles can represent Azure OAuth users/SPs with secure refresh-token caching.

**Files**: `src/pacx/config.py`, `src/pacx/cli/profile.py`, `tests/config/`, `tests/cli/`

**Acceptance**
- Legacy configs load (missing fields default safely).
- `refresh_token` is encrypted at rest and masked in CLI.
- Unit tests cover defaults + encryption round-trip.

**Subtasks**
1. Extend the profile dataclass to capture refresh tokens and preferred interactive flow flags.
2. Wire new fields into serialization/deserialization logic with migration coverage for pre-existing configs.
3. Update CLI profile rendering to redact sensitive values and expose flow hints.
4. Author regression tests for legacy payloads, encrypted storage, and CLI masking behavior.

**Codex prompt**
```text
Edit src/pacx/config.py and src/pacx/cli/profile.py:

1) In Profile dataclass add:
   - refresh_token: str | None = None
   - use_device_code: bool = True  # remember chosen user flow

2) Add "refresh_token" to SENSITIVE_KEYS so it is encrypted/masked like access_token.

3) Ensure ConfigStore.load() handles legacy profiles (no new fields) by relying on dataclass defaults.

4) Tests:
   - tests/config/test_profile_defaults.py: legacy JSON -> use_device_code True, refresh_token None.
   - tests/config/test_profile_encryption.py: with PACX_CONFIG_ENCRYPTION_KEY set, saving a refresh_token stores enc:<...> and decrypts back.
   - tests/cli/test_profile_show_mask.py: CLI masks refresh_token.

Run ruff/black/mypy/pytest.
```

---

## P0.2 Azure AD provider: device + auth-code + client-credentials + refresh
**Goal**: One provider handles all flows and refreshes silently if possible.

**Files**: `src/pacx/auth/azure_ad.py`, `tests/auth/test_azure_oauth.py`

**Acceptance**
- Refresh grant used when refresh_token exists; falls back to interactive if refresh fails.
- Device flow prints only verification URL/code; no secrets.
- Browser (auth-code) flow works (stubbed in tests).
- Client creds unchanged and still pass.
- Tests cover refresh success/fail → device fallback; interactive success/fail; client creds.

**Subtasks**
1. Introduce a dedicated helper that orchestrates refresh-token attempts before interactive flows.
2. Normalize token persistence (access/refresh) so all successful flows update the profile & config store atomically.
3. Build structured logging/messages that surface verification instructions without leaking secrets.
4. Cover refresh, device, interactive, and client credential scenarios with respx/MSAL stubs in unit tests.

**Codex prompt**
```text
Refactor src/pacx/auth/azure_ad.py (AzureADTokenProvider):

1) If profile has refresh_token, POST to AAD token endpoint (v2) with grant_type=refresh_token to get a new access_token (+ optional new refresh_token). On success, persist tokens to config.

2) If refresh absent/fails:
   - If use_device_code: run device flow (existing MSAL path), print flow["message"], save access/refresh tokens to profile.
   - Else: run acquire_token_interactive() to open browser and capture tokens; save to profile.

3) Client credentials flow unchanged (acquire_token_for_client).

4) Raise AuthError on terminal failures. No secrets printed.

5) Tests (tests/auth/test_azure_oauth.py):
   - refresh success (respx) → returns new access_token; profile updated.
   - refresh 400 → device fallback path exercised (stub MSAL device to return token).
   - interactive success/fail stubs.
   - client creds regression test.

Run ruff/black/mypy/pytest.
```

---

## P0.3 Unified CLI: `ppx auth create`
**Goal**: One command to create/login profiles (device, web, or client credentials).

**Files**: `src/pacx/cli/auth.py` (or `auth_create.py`), `src/pacx/cli/__init__.py`, `tests/cli/test_auth_create.py`, docs.

**Acceptance**
- `ppx auth create NAME` supports `--tenant-id`, `--client-id`, `--scopes`, `--web/--device`, client secret via env/keyring/KeyVault flags.
- Auth happens immediately; on success profile saved (optional `--no-set-default`).
- Old commands remain as aliases (deprecated in help).

**Subtasks**
1. Build a consolidated Typer command that maps CLI options to provider flow selection.
2. Implement secret sourcing helpers (env, keyring, KeyVault, prompt) with validation and clear error messages.
3. Persist new profiles, respecting default profile semantics and backwards compatibility with legacy commands.
4. Update CLI documentation/help text and add targeted unit tests for device, web, and client credential permutations.

**Codex prompt**
```text
Add unified auth command:

1) Create/extend src/pacx/cli/auth.py with @auth_app.command("create"). Options:
   - --tenant-id TEXT (req), --client-id TEXT (req)
   - --scopes TEXT (default "https://api.powerplatform.com/.default")
   - --web/--device (default device)
   - --client-secret-env TEXT | --secret-backend [env|keyring|keyvault] --secret-ref TEXT | --prompt-secret
   - --dataverse-host TEXT
   - --set-default/--no-set-default (default True)

2) Determine flow:
   - If any secret provided → client credentials.
   - Else → user flow; device unless --web.

3) Call AzureADTokenProvider.get_token(); on success persist profile (tokens saved via provider).

4) Keep auth device/client as aliases (mark deprecated).

5) Tests (tests/cli/test_auth_create.py):
   - device (default) → stub provider returns token; profile saved; default set.
   - web → use_device_code False stored.
   - client creds → secret via env; profile references env; token path called.
   - --no-set-default keeps prior default.

Update docs to prefer `ppx auth create`.
```

---

## P0.4 Token resolution precedence
**Goal**: Use best available token automatically.

**Files**: `src/pacx/cli/common.py` (or `cli_utils.py`), `tests/cli/test_token_resolution.py`

**Precedence**
1. `PACX_ACCESS_TOKEN` env
2. Keyring (secret_backend/secret_ref)
3. Encrypted config (`access_token`)
4. Provider.get_token() (refresh → interactive)

**Subtasks**
1. Extend token lookup utility to consider environment variables, keyring, and encrypted config sequentially.
2. Teach the resolver to invoke the AzureADTokenProvider when cached values are absent/expired and persist refreshed tokens.
3. Add unit tests for each branch, including failure propagation via `AuthError`.
4. Document override order in both code comments and CLI docs.

**Codex prompt**
```text
Extend token resolution to:
- Check env override first.
- If profile has secret_backend+secret_ref, fetch token from keyring.
- Else if access_token present, return it.
- Else instantiate AzureADTokenProvider (with profile.use_device_code) and return provider.get_token.

Add tests for each branch.
```

---

## P0.5 Keyring-first refresh storage
**Goal**: Prefer secure OS keyrings for refresh tokens while retaining encrypted-config fallback.

**Files**: `src/pacx/config.py`, `src/pacx/secrets.py`, `tests/config/test_refresh_keyring.py`, `tests/secrets/test_refresh_keyring.py`

**Acceptance**
- When keyring is available, refresh tokens write/read from keyring using deterministic refs per profile.
- Config falls back to encrypted storage when keyring is unavailable, with clear telemetry.
- Tests cover both keyring-present and keyring-absent scenarios.

**Subtasks**
1. Introduce deterministic keyring references (e.g., `profile:<name>:refresh_token`) to persist refresh tokens securely.
2. Update config save/load logic to route refresh tokens through keyring when configured.
3. Emit structured warnings when falling back to encrypted config, ensuring no secret leakage.
4. Build unit tests that monkeypatch keyring availability to validate both branches.

---

# P1 — Security, docs, UX

## P1.1 `set_secret()` helper
**Goal**: Symmetric writer for keyring storage.

**Files**: `src/pacx/secrets.py`, `tests/secrets/test_set_secret.py`

**Acceptance**
- Stores to keyring (service: "pacx", username: ref).
- Graceful error if keyring missing.

**Subtasks**
1. Implement helper that abstracts keyring writes with consistent error handling and logging.
2. Ensure helper integrates with existing secret backends without duplicating logic.
3. Unit test success and failure paths using monkeypatched keyring modules.

**Codex prompt**
```text
Implement set_secret(backend, ref, value) for keyring; raise informative error if not available.
Add unit tests with monkeypatched keyring.
```

---

## P1.2 Documentation
**Goal**: Add/refresh auth docs & CLI help.

**Files**: `docs/user-manual/02-authentication.md`, `docs/user-manual/03-cli-usage.md`

**Content**
- `ppx auth create` examples for device, web, client creds.
- Multi-profile usage (`profile list`, `auth use`).
- Token storage/refresh notes, security guidance.

**Subtasks**
1. Rewrite authentication chapter to center on unified auth flows, including headless vs desktop guidance.
2. Embed runnable snippets demonstrating each flow with surrounding CLI context.
3. Add troubleshooting section covering common Azure AD errors and recommended flags.
4. Verify mkdocs build locally and update navigation if needed.

**Codex prompt**
```text
Update docs to cover unified auth command, flows, examples, and security notes. Ensure docs build clean.
```

---

## P1.3 Error guidance
**Goal**: Friendly hints when auth fails.

**Files**: `src/pacx/cli/common.py`, `tests/cli/test_errors.py`

**Subtasks**
1. Extend `handle_cli_errors` to detect `AuthError` instances and surface actionable remediation text.
2. Confirm new messaging respects logging redaction rules and remains translatable/localizable.
3. Update error-handling tests to capture new hint output without leaking tokens.

**Codex prompt**
```text
In handle_cli_errors, if AuthError, print a concise hint:
- "Run `ppx auth create` to (re)authenticate (use --device in headless shells)."
Add/adjust tests.
```

---

## P1.4 Headless & CI guidance
**Goal**: Document and validate non-interactive authentication strategies.

**Files**: `docs/user-manual/02-authentication.md`, `docs/user-manual/04-ci-examples.md`, `tests/cli/test_ci_examples.py`

**Acceptance**
- Provide cookbook for using client credentials and device code within CI environments.
- Include sample scripts/snippets validated by tests (where feasible with mocks).
- Ensure docs address secret management recommendations for pipelines.

**Subtasks**
1. Draft CI-focused guide highlighting environment variables, key vault integration, and token caching considerations.
2. Create simple mocked tests that verify documented scripts remain accurate.
3. Link CI guidance from authentication overview and README quickstart sections.

---

# P2 — Optional polish

## P2.1 Alias: `ppx login`
**Goal**: Friendly entry that routes to `auth create` with provider defaults.

**Files**: `src/pacx/cli/login.py` (or same module), tests.

**Subtasks**
1. Implement Typer command `login` delegating to the unified auth handler with sensible defaults.
2. Add smoke tests confirming alias behavior and deprecation messaging for legacy commands.

**Codex prompt**
```text
Add ppx login alias delegating to `auth create` (device by default). Keep help minimal; link to auth docs.
```

## P2.2 Packaging extras
**Goal**: Keep deps minimal; expose optional extras.

**Files**: `pyproject.toml`

**Subtasks**
1. Ensure `httpx` and auth-centric dependencies are correctly declared and pinned as needed.
2. Introduce optional extras for auth helpers (`auth = ["keyring", "cryptography"]`) if missing.
3. Update packaging tests or lockfiles to reflect new extras.

**Codex prompt**
```text
Ensure httpx present. Add optional extra `auth = ["keyring", "cryptography"]` if not already defined.
```

## P2.3 Quickstart samples
**Goal**: Provide runnable notebooks/scripts demonstrating OAuth flows end-to-end.

**Files**: `docs/examples/oauth_device_flow.ipynb`, `docs/examples/oauth_client_credentials.py`

**Acceptance**
- Samples align with new CLI commands and shareable prompts.
- Scripts include instructions for obtaining tokens and calling Dataverse endpoints.
- Optional: include screenshot assets for docs.

**Subtasks**
1. Author minimal notebook covering device-code login and basic API call using stored tokens.
2. Provide CLI-first Python script using client credentials for automation scenarios.
3. Reference these artifacts from documentation and ensure they stay in sync with automated tests or linting.

---

# Validation & Release

## V.1 Smoke + snapshots
**Goal**: Lock CLI UX and avoid regressions.

**Codex prompt**
```text
Add snapshot tests for `ppx auth create --help` and a mocked device flow happy path.
```

**Subtasks**
1. Capture CLI help output snapshots with approvals tooling (pytest + syrupy or similar).
2. Build high-level smoke test orchestrating a device flow using mocks to ensure CLI narratives stay stable.

## V.2 CHANGELOG + version bump
**Codex prompt**
```text
Create/update CHANGELOG.md with "feat(auth): unified OAuth (device/web/client creds) + refresh & profiles".
Bump version; tag release; ensure CI publish passes.
```

**Subtasks**
1. Draft changelog entry summarizing major auth features and migration notes.
2. Increment library version (semver minor) and verify packaging metadata.
3. Coordinate release checklist: tests, docs build, tag preparation.

---

## One-paste “mega prompt”

```text
Implement OAuth like `pac` CLI with device, auth-code, and client-credentials flows; secure refresh; unified CLI `ppx auth create`; token precedence; docs; tests.

Files
- src/pacx/config.py (refresh_token, use_device_code, sensitive keys)
- src/pacx/auth/azure_ad.py (refresh → interactive/device; client creds unchanged)
- src/pacx/cli/auth.py (create command; deprecate old ones)
- src/pacx/cli/common.py (token resolution precedence)
- src/pacx/secrets.py (set_secret)
- tests/... (auth provider, CLI create, token resolution, secrets)
- docs/user-manual/02-authentication.md, 03-cli-usage.md
- pyproject.toml (optional extra)

Acceptance
- ruff/black/mypy/pytest green.
- Device flow prints only instructions; browser flow works; client creds path unchanged.
- Refresh tokens persist encrypted; resolution precedence respected.
- `ppx auth create` UX is clear; docs updated.
```
