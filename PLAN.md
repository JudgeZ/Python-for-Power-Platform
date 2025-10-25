# PLAN.md — GitHub OAuth (Unified Login) Implementation Plan

This plan contains **copy/paste Codex prompts** to add **GitHub OAuth 2.0** to the repo with a **single, unified login UX**.
It keeps changes **small, testable, and reversible**, and aligns with the project’s existing patterns (Typer CLI, HttpClient, ConfigStore, keyring/crypto).

---

## Global conventions for all prompts

- Keep public APIs backward compatible unless stated (deprecate gently, don’t break).
- Strictly maintain: `ruff`, `black`, `mypy`, `pytest -q` → green.
- Use existing error plumbing (`handle_cli_errors`) and `Rich`-style messages.
- Prefer the shared `HttpClient` abstraction (backed by httpx) over direct HTTP client usage.
- **Never print secrets**. Mask tokens in logs; store in keyring or encrypted config.
- For each task, update docs and write tests. Small, focused commits using Conventional Commits.
- Keep `pip-audit` and `bandit` clean when touching dependency or security-sensitive code.

---

# P0 — Core authentication support

## P0.1 Add provider awareness to profiles (config)
**Goal**: Allow multiple identity providers; support GitHub tokens & (optional) refresh tokens.

**Files**: `src/pacx/config.py`, `src/pacx/secrets.py` (if needed), tests under `tests/config/`.

**Changes**
- Extend `Profile` to include:
  - `provider: Literal["azure","github"] = "azure"` (default azure for backward compat)
  - `refresh_token: str | None = None` (sensitive)
- Keep using the existing `scopes: list[str] | None = None` field (already defined alongside `scope`).
- Add `"refresh_token"` into the sensitive keys set so it is encrypted at rest (just like `access_token`).
- On load, **default** missing `provider` to `"azure"` for old configs.
- (If not present) add a small, internal `set_secret(backend, ref, value)` helper symmetrical to `get_secret`.

**Acceptance**
- Loading legacy configs (no `provider`) yields `provider="azure"`.
- New profiles round-trip correctly (JSON + encryption for sensitive fields).
- Tests demonstrate: legacy load default, encryption of `refresh_token` if present.

**Codex prompt**
```text
Edit src/pacx/config.py:

1) In Profile dataclass, add or confirm:
   - provider: Literal["azure","github"] = "azure"
   - refresh_token: str | None = None

   (The scopes field already exists; continue using it as-is.)

2) Ensure "refresh_token" is included in the SENSITIVE_KEYS so it is encrypted/decrypted like access_token.

3) In ConfigStore.load(), when materializing Profile instances, default provider to "azure" if missing (back-compat).

4) Add/verify tests:
   - tests/config/test_profile_provider_defaults.py
     * load legacy JSON (no provider) -> Profile.provider == "azure"
   - tests/config/test_profile_sensitive_fields.py
     * ensure refresh_token is encrypted/decrypted when PACX_CONFIG_ENCRYPTION_KEY is set.

Run: ruff/black/mypy/pytest.
```

---

## P0.2 Implement GitHub OAuth provider (device + auth-code, optional refresh)
**Goal**: New `GitHubTokenProvider` with **Device Code** and **Authorization Code** flows using the shared `HttpClient`.

**File**: `src/pacx/auth/github.py` (new). Tests: `tests/auth/test_github_oauth.py`.

**Key behaviors**
- Public API: `GitHubTokenProvider(client_id, scopes, client_secret: str|None=None, use_device_code: bool=False, redirect_uri: str|None=None)`
- Method: `get_token() -> str` (caches in-memory; tries refresh if a refresh token is present).
- **Device Code flow**:
  - POST `https://github.com/login/device/code` with `client_id`, `scope` (space-joined).
  - Print “Open {verification_uri} and enter code: {user_code}” (no secrets).
  - Poll `https://github.com/login/oauth/access_token` with `client_id`, `device_code`, `grant_type=urn:ietf:params:oauth:grant-type:device_code` until `access_token` or terminal error.
  - Handle `authorization_pending`, `slow_down` (+5s), `expired_token` clearly.
- **Auth Code flow**:
  - Open browser to `https://github.com/login/oauth/authorize` with `client_id`, `scope` (and `redirect_uri` if provided).
  - If `redirect_uri` is localhost, capture code via a minimal local socket listener; else prompt user to paste `code`.
  - Exchange code: POST `https://github.com/login/oauth/access_token` with `client_id`, `client_secret`, `code`, and `redirect_uri` if used.
- **Refresh (optional)**:
  - If `refresh_token` present, POST token refresh with `grant_type=refresh_token` to the same token endpoint.
- Raise `AuthError` for any failure; never print tokens.

**Acceptance**
- Unit tests mock endpoints (respx) for:
  - Happy device flow (pending → success).
  - slow_down and expired_token branches.
  - Auth code exchange happy path + error.
  - Optional refresh (if refresh_token returned by mock).
- Type hints + docstrings present; ruff/black/mypy clean.

**Codex prompt**
```text
Create src/pacx/auth/github.py with class GitHubTokenProvider implementing:
- __init__(client_id, scopes, client_secret: str|None=None, use_device_code: bool=False, redirect_uri: str|None=None)
- get_token() -> str
- private helpers for device flow, auth code flow, and refresh if refresh_token exists.

Constraints:
- Use the shared HttpClient abstraction. Set "Accept: application/json".
- Print only user instructions (verification_uri + user_code). Do not print tokens.
- Raise pacx.errors.AuthError on failures.

Add tests in tests/auth/test_github_oauth.py using respx:
- device flow success (authorization_pending → access_token).
- device flow slow_down behavior (interval increases).
- device flow expired_token -> AuthError.
- auth code exchange success and error.
- refresh token path (mock returns refresh_token then new access_token).

Run ruff/black/mypy/pytest.
```

---

## P0.3 CLI: `ppx auth github` (unified login entry)
**Goal**: Add a single CLI entry for GitHub login with flags that cover both flows.

**File**: `src/pacx/cli/auth_github.py` (new) or extend existing `auth.py`. Register in `src/pacx/cli/__init__.py`.

**CLI signature**
- `ppx auth github <profile>`
  - `--client-id TEXT` (required)
  - `--client-secret TEXT` (optional; triggers web flow if provided or with `--web`)
  - `--scopes "repo gist read:org"` (default `"repo"`)
  - `--web/--device` (default device)
  - `--redirect-uri TEXT` (for localhost capture; optional)
  - `--save-secret` (store client-secret in keyring; otherwise recommend env)
  - `--set-default/--no-set-default` (default: set-default)

**Behavior**
- Resolve scopes list (split on comma/space). If empty, interactively suggest common scopes (optional).
- Instantiate `GitHubTokenProvider` with chosen flow; call `get_token()`.
- Persist tokens securely:
  - Prefer keyring via `set_secret("keyring", f"github-{profile}-token", token)`.
  - If keyring unavailable, store `access_token` (and `refresh_token`) in Profile (encrypted at rest).
- Create/update Profile with `provider="github"`, `client_id`, `scopes`, and secret references.
- Print friendly success message; on AuthError, show concise guidance.

**Acceptance**
- `ppx auth github --help` renders complete help.
- Running command stores tokens securely and sets profile default (unless `--no-set-default`).
- Tests cover CLI happy paths and error flows (CliRunner + respx mocks).

**Codex prompt**
```text
Add new CLI command for GitHub auth.

1) Create src/pacx/cli/auth_github.py with a Typer app and command "github".
   - Arguments/options: profile, --client-id, --client-secret, --scopes, --web/--device, --redirect-uri, --save-secret, --set-default/--no-set-default.
   - Use GitHubTokenProvider; on success, persist tokens securely (keyring preferred; else in encrypted config).

2) Register sub-app in src/pacx/cli/__init__.py (e.g., app.add_typer(auth_github_app, name="auth")).
   If an auth group already exists, add command "github" within it.

3) Tests: tests/cli/test_auth_github_cli.py
   - mock device flow; assert console shows verification_uri/user_code message; profile created; token stored.
   - mock auth code flow; assert browser open stub called or URL printed; profile created.
   - simulate keyring failure to force config storage path.
   - ensure --no-set-default keeps prior default intact.

Run ruff/black/mypy/pytest.
```

---

## P0.4 Token resolution: support `provider="github"`
**Goal**: Make `resolve_token_getter` (or equivalent) return a GitHub token when the default profile is GitHub.

**Files**: `src/pacx/cli/common.py` or `src/pacx/cli/cli_utils.py`, tests in `tests/cli/`.

**Behavior**
- Precedence: `PACX_ACCESS_TOKEN` (env) → stored secret via keyring → config `access_token` → interactive provider fallback.
- If profile.provider == "github":
  - Fetch token from keyring if `secret_backend=="keyring"` + `secret_ref` present.
  - Else, if config has `access_token`, return it.
  - Else, instantiate `GitHubTokenProvider` with `client_id`, `scopes` (from profile), `client_secret` from env if `client_secret_env` set, and `use_device_code` when no secret.
- For Azure profiles: current behavior unchanged.
- Error: clear BadParameter if required fields missing (e.g., no client_id).

**Acceptance**
- New tests verify token resolution for github profiles (keyring path, config path, provider fallback).
- No regressions for azure profiles.

**Codex prompt**
```text
Extend token resolution for GitHub.

1) In src/pacx/cli/common.py (or cli_utils), add branch for profile.provider == "github".
2) Implement precedence: env -> keyring -> config -> provider.get_token().
3) Read client_secret from env if profile.client_secret_env is set.
4) Use profile.scopes (list) when instantiating provider.

Tests in tests/cli/test_token_resolution_github.py:
- env overrides all.
- keyring hit returns lambda.
- config access_token returns lambda.
- fallback calls provider.get_token() (mock provider).

Run ruff/black/mypy/pytest.
```

---

# P1 — Secure storage, docs, and UX polish

## P1.1 Secrets persistence helper
**Goal**: Provide `set_secret()` to complement `get_secret()` for keyring/kv, with graceful fallback.

**Files**: `src/pacx/secrets.py`, tests `tests/secrets/`.

**Behavior**
- Implement `set_secret(backend: Literal["keyring","keyvault"], ref: str, value: str) -> None`.
- Keyring path: use `keyring.set_password(service, username, value)`; pick stable service/username scheme (e.g., service `"pacx"`, username=ref).
- KeyVault path: optional (if existing code already supports reads, leave write as NotImplemented).
- Raise informative errors; do not print values.

**Acceptance**
- tests: keyring happy path (monkeypatch keyring), error path (no keyring).

**Codex prompt**
```text
Add set_secret() in src/pacx/secrets.py and tests in tests/secrets/test_set_secret.py.
Use keyring if available, otherwise raise a clear exception. Do not log secret values.
```

---

## P1.2 Documentation: GitHub OAuth
**Goal**: Add GitHub auth docs with quick start and flows.

**Files**: `docs/user-manual/02-authentication.md` (extend), `docs/user-manual/10-github-oauth.md` (new), `docs/user-manual/03-cli-usage.md` (link).

**Content**
- How to create a GitHub OAuth App (Client ID/Secret; enabling device flow; callback URI for auth code).
- Examples:
  - Device flow: `ppx auth github <profile> --client-id ... --scopes "repo gist"`
  - Web flow: `ppx auth github <profile> --client-id ... --client-secret ... --web --redirect-uri http://localhost:8765/callback`
  - CI fallback: `PACX_ACCESS_TOKEN` usage.
- Storage and security notes (keyring preferred, encryption fallback).

**Acceptance**
- Docs build without warnings; examples copy/paste successfully (with placeholders).

**Codex prompt**
```text
Update docs:
- Extend 02-authentication.md with "GitHub OAuth" section.
- Add 10-github-oauth.md with step-by-step setup and examples.
- Link from 03-cli-usage.md and README to new section.

Include screenshots/ASCII where helpful. Ensure consistency with CLI help text.
```

---

## P1.3 CLI error messaging
**Goal**: If auth fails and default profile is GitHub, suggest `ppx auth github` explicitly.

**Files**: `src/pacx/cli/common.py`, tests `tests/cli/test_errors.py`.

**Acceptance**
- On `AuthError` with github provider, message includes `ppx auth github` guidance.
- Tests assert message text.

**Codex prompt**
```text
Amend handle_cli_errors to add GitHub guidance:
- If provider == "github" or token resolution fails in github branch, print:
  "Run `ppx auth github <profile>` to (re)authenticate."
Add/adjust tests accordingly.
```

---

# P2 — Optional unified alias & CI/packaging

## P2.1 Unified alias: `ppx login`
**Goal**: User-friendly alias that chooses provider by flag or infers from default profile.

**Files**: `src/pacx/cli/login.py` (new) or extend `auth.py`.

**Behavior**
- `ppx login --provider azure|github [other flags]` routes to appropriate subcommand.
- If `--provider` omitted, and a default profile exists, infer provider and call its auth command with best-effort defaults.

**Acceptance**
- Help text is clear; tests show azure/github routing works.

**Codex prompt**
```text
Add ppx login alias:
- Implement simple router command that delegates to auth azure/device or auth github based on --provider or current default profile.provider.
- Keep docs minimal; link to full auth sections.
```

---

## P2.2 Packaging updates (only if needed)
**Goal**: Ensure dependencies are present and extras are meaningful.

**Files**: `pyproject.toml`.

**Changes (only if missing)**
- Ensure `httpx` already present (use it for OAuth HTTP calls).
- Optional extra `[project.optional-dependencies] auth = ["keyring", "cryptography"]` (if not already present).
- Do **not** add heavy OAuth deps unless necessary (we use HttpClient/httpx combo).

**Acceptance**
- Build and tests pass in CI; no new CVEs (`pip-audit` stays green).

**Codex prompt**
```text
Inspect pyproject.toml:
- Confirm httpx installed.
- If needed, add extra 'auth' with keyring and cryptography.
- Do not add new HTTP libs; rely on existing HttpClient wrapper.

Run packaging checks in CI.
```

---

# Validation & release

## V.1 Tests, smoke, and golden outputs
**Goal**: Lock in behavior; prevent regressions.

**Tasks**
- Add snapshot tests (optional) for help text of `ppx auth github --help`.
- End-to-end smoke in CI job (can be mocked; ensure exit code 0 and expected messages appear).

**Codex prompt**
```text
Add snapshot tests for CLI help output and a smoke test invoking ppx auth github with mocked device flow endpoints.
```

---

## V.2 Changelog & version bump
**Goal**: Document the new feature and cut a release.

**Files**: `CHANGELOG.md`, `pyproject.toml`.

**Tasks**
- Add entry “feat(auth): GitHub OAuth with unified CLI login” + highlights (device & auth-code, secure storage, docs).
- Bump minor/major version as agreed (e.g., 0.x → 1.0 if this is the last blocker).

**Codex prompt**
```text
Update CHANGELOG.md and bump version in pyproject.toml.
Create a tag and verify publish/docs workflows pass.
```

---

## Quick execution order (suggested)

### Status
- [ ] **P0.1 (Active)** – Config/provider updates are still pending while GitHub-specific modules have not been introduced, so the task remains open.
- [ ] P0.2
- [ ] P0.3
- [ ] P0.4
- [ ] P1.1
- [ ] P1.2 / P1.3
- [ ] P2.1 / P2.2
- [ ] V.1 / V.2

1) P0.1 (config provider + sensitive fields)
2) P0.2 (GitHubTokenProvider + tests)
3) P0.3 (CLI command + tests)
4) P0.4 (token resolution + tests)
5) P1.1 (set_secret helper + tests)
6) P1.2 (docs) & P1.3 (messaging)
7) P2.1 (login alias) & P2.2 (packaging if needed)
8) V.1/V.2 (smoke + release)

---

## Copy-ready mega prompt (all-in-one, if you prefer)

```text
You are a senior Python engineer. Implement GitHub OAuth 2.0 support (device+auth code) with a unified CLI login for this repository. Keep changes small and additive.

Scope
- Add provider-aware Profile (azure|github), scopes list, and refresh_token (sensitive).
- New src/pacx/auth/github.py with GitHubTokenProvider using HttpClient, supporting device flow and authorization code flow (+ optional refresh).
- CLI: ppx auth github <profile> with flags for client-id, client-secret, scopes, web/device, redirect-uri, save-secret, set-default.
- Token resolution: support provider="github" including env → keyring → config → provider flow.
- Secure persistence via keyring (preferred) or encrypted config fallback (existing encryption).
- Docs for GitHub OAuth; update error hints to mention ppx auth github.
- Tests for provider, CLI, token resolution, and OAuth flows (respx).

Files to create/edit
- src/pacx/config.py (Profile fields; sensitive keys; defaults)
- src/pacx/auth/github.py (new)
- src/pacx/cli/auth_github.py (or extend existing auth module)
- src/pacx/cli/__init__.py (register command)
- src/pacx/cli/common.py or cli_utils.py (token resolution changes)
- src/pacx/secrets.py (set_secret helper if missing)
- tests/auth/test_github_oauth.py; tests/cli/test_auth_github_cli.py; tests/cli/test_token_resolution_github.py
- docs/user-manual/02-authentication.md; docs/user-manual/10-github-oauth.md; docs/user-manual/03-cli-usage.md

Acceptance
- ruff/black/mypy/pytest all pass.
- Device flow prints verification URL/code and returns token (mocked).
- Auth code flow opens URL or prints it and exchanges code (mocked).
- Tokens persisted securely (keyring when available).
- `ppx auth github --help` is complete; error messages suggest ppx auth github on failures.
- Docs build without warnings.

Do not expose secrets; never print tokens. Keep commits atomic with Conventional Commits.
```
