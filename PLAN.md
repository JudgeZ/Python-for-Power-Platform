# PLAN.md — Codex Implementation Plan (Tasks & Subtasks)

This plan is designed for a code-generation assistant ("Codex/agent") to **implement** and **finish** repository improvements end-to-end.
It includes **granular tasks**, **subtasks**, **explicit file paths**, **acceptance criteria**, and **copy/paste-ready prompts**.
Adjust paths if your repo layout differs (defaults assume: `src/pacx/...`, tests under `tests/...`, docs under `docs/...`).

---

## Global Conventions for All Tasks

- **Tooling**: Keep green `ruff`, `black`, `mypy`, `pytest`. Do not introduce new warnings.
- **Safety**: Maintain backward compatibility for public APIs unless explicitly marked `BREAKING`. Provide deprecation shims/messages.
- **Commits**: Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. One logical change per commit.
- **Docs**: Update CLI `--help` and pages under `docs/user-manual/` whenever user-visible behavior changes.
- **Tests**: Add/adjust tests with each change. Prefer deterministic, isolated tests (tmp dirs, mocks, snapshot filtering).
- **Validation** (per task): Run `ruff --fix . && black . && mypy . && pytest -q`, then verify `ppx --help` and relevant subcommand help.

---

# Shared Execution Plan — GitHub OAuth Unified Login

The next milestone introduces GitHub as a first-class identity provider while
preserving the existing Azure experience. Work is grouped into high-impact
increments so we can land and verify changes independently.

## P0 — Core authentication support

### P0.1 Add provider awareness to profiles (config)
**Goal**: Extend profile records so they can describe the issuing identity
provider and any provider-specific scope/refresh metadata.

**Files**: `src/pacx/config.py`, `src/pacx/secrets.py` (helper),
`tests/config/`.

**Subtasks**
1. Update the `Profile` dataclass with `provider`, `scopes`, and
   `refresh_token` fields while defaulting legacy records to Azure.
2. Mark `refresh_token` as sensitive so the existing encryption pipeline keeps
   it secure at rest.
3. Add a `set_secret()` helper that mirrors `get_secret()` for writing to the
   configured secrets backend (keyring-first, with helpful errors when
   unavailable).
4. Tests: coverage for legacy profile loading, encrypted refresh tokens, and
   the new helper.

**Acceptance Criteria**
- Loading an existing config without `provider` yields `provider == "azure"`.
- New profiles persist and reload with GitHub metadata intact.
- Sensitive fields (`access_token`, `refresh_token`) stay encrypted in the
  config file when encryption is enabled.
- Unit tests in `tests/config/` and `tests/secrets/` assert the above.

### P0.2 Implement GitHub token provider (device + auth-code flows)
**Goal**: Introduce `GitHubTokenProvider` that supports device-code and web
authorization flows using the project `HttpClient` abstraction (no direct
httpx usage) and reusable error plumbing.

**Files**: `src/pacx/auth/github.py` (new), `tests/auth/test_github_oauth.py`.

**Subtasks**
1. Implement provider constructor accepting client id/secret, scopes, flow
   selection, and redirect URI.
2. Device flow: request/poll endpoints, surface user instructions, and respect
   interval/back-off guidance.
3. Authorization-code flow: launch browser helper, capture/prompt for the code
   (localhost listener optional), and exchange for tokens.
4. Optional refresh-token exchange when a refresh token exists.
5. Tests: mock happy path, slow down, expired token, auth-code error, and
   refresh exchange via `respx`.

**Acceptance Criteria**
- Provider caches valid access tokens and refreshes when needed.
- Errors raise `AuthError` with actionable messaging (no token logging).
- Test suite exercises all branches with deterministic timings.

### P0.3 CLI: `ppx auth github`
**Goal**: Add a Typer-powered entry point for GitHub authentication that reuses
shared helpers and respects secure storage conventions.

**Files**: `src/pacx/cli/auth_github.py` (new), `src/pacx/cli/__init__.py`,
`src/pacx/cli/common.py` (if registration tweaks required),
`tests/cli/test_auth_github_cli.py`.

**Subtasks**
1. Define CLI options (`--client-id`, `--client-secret`, `--scopes`,
   `--web/--device`, `--redirect-uri`, `--save-secret`,
   `--set-default/--no-set-default`).
2. Resolve scopes (split on comma/space) and instantiate
   `GitHubTokenProvider` with the correct flow configuration.
3. Persist tokens via `set_secret()` when keyring is available, otherwise fall
   back to encrypted config fields.
4. Update/create profiles with `provider="github"` and scope metadata; respect
   `--no-set-default`.
5. Tests: CLI happy path (device & web), keyring failure fallback, and
   `--no-set-default` behavior.

**Acceptance Criteria**
- `ppx auth github --help` documents all options.
- Tokens store securely with friendly success messaging.
- CLI tests cover success/failure flows without leaking secrets.

### P0.4 Token resolution updates
**Goal**: Teach token resolution helpers to honor GitHub-backed profiles while
preserving Azure behavior.

**Files**: `src/pacx/cli/common.py` (or the shared resolver module),
`tests/cli/test_token_resolution_github.py`.

**Subtasks**
1. Extend resolver precedence: env var → keyring → config → provider fetch for
   GitHub profiles.
2. Pull client secrets from configured env vars when present.
3. Instantiate `GitHubTokenProvider` lazily for the fallback branch.
4. Tests: env override, keyring hit, config fallback, provider invocation.

**Acceptance Criteria**
- GitHub profiles return callable token getters consistent with Azure logic.
- Resolver emits actionable errors when required metadata is missing.
- New tests prove each branch and avoid regressions for Azure paths.

### P0.5 Error messaging polish
**Goal**: Ensure GitHub-authenticated users receive tailored remediation tips
when token acquisition fails.

**Files**: `src/pacx/cli/common.py`, `tests/cli/test_errors.py`.

**Subtasks**
1. Detect GitHub provider failures inside `handle_cli_errors` (or equivalent).
2. Surface “Run `ppx auth github <profile>` to (re)authenticate.” guidance.
3. Tests validating the new hint appears only for GitHub contexts.

**Acceptance Criteria**
- Existing Azure messaging remains unchanged.
- GitHub failures prompt the new actionable guidance.
- Tests demonstrate message specificity.

## P1 — Secure storage, docs, and UX polish

### P1.1 Secrets persistence helper hardening
**Goal**: Finalize `set_secret()` ergonomics, documenting supported backends
and graceful fallbacks.

**Files**: `src/pacx/secrets.py`, `tests/secrets/`, docs updates under
`docs/user-manual/`.

**Subtasks**
1. Expand helper docstrings, emphasizing keyring usage and error modes.
2. Provide docs snippet showing how CLI flags interact with keyring storage.
3. Add negative-path tests (e.g., keyring import error) with helpful messages.

**Acceptance Criteria**
- Helper behavior is clearly documented and fully covered by tests.
- Docs explain security posture and troubleshooting.

### P1.2 Documentation for GitHub OAuth
**Goal**: Author a dedicated guide covering device and web flows along with
configuration tips.

**Files**: `docs/user-manual/02-authentication.md`,
`docs/user-manual/10-github-oauth.md` (new),
`docs/user-manual/03-cli-usage.md`, `README.md` (links), tests if docs have
doctests.

**Subtasks**
1. Extend authentication overview with GitHub provider summary.
2. Create the dedicated GitHub OAuth guide (app registration, CLI examples,
   CI guidance).
3. Cross-link from CLI usage docs and README for discoverability.

**Acceptance Criteria**
- Documentation builds without warnings and matches CLI flags.
- Examples are copy/paste ready with placeholder markers for secrets.

### P1.3 CLI help snapshots & smoke tests
**Goal**: Capture `ppx auth github --help` output and add a mocked smoke test to
guard against regressions.

**Files**: `tests/cli/test_auth_github_cli.py`, snapshot fixtures as needed.

**Subtasks**
1. Snapshot help output to lock flag descriptions.
2. Introduce an end-to-end smoke test with mocked device endpoints ensuring the
   CLI prints verification instructions and exits cleanly.

**Acceptance Criteria**
- Snapshots updated intentionally when help text changes.
- Smoke test runs in CI without hitting real GitHub services.

## P2 — Unified alias & release readiness

### P2.1 `ppx login` alias
**Goal**: Provide a top-level login command that delegates to provider-specific
flows based on flags or the default profile.

**Files**: `src/pacx/cli/login.py` (new) or existing auth router,
`src/pacx/cli/__init__.py`, docs references, `tests/cli/test_login_alias.py`.

**Subtasks**
1. Implement the router command using Typer that forwards to Azure or GitHub
   auth handlers.
2. Respect `--provider` overrides and default profile inference.
3. Tests ensuring delegation works and help text is clear.

**Acceptance Criteria**
- `ppx login --help` documents routing semantics.
- Alias defers to provider commands without duplicating logic.
- Unit tests cover Azure and GitHub paths.

### P2.2 Packaging & changelog updates
**Goal**: Confirm dependencies and metadata reflect the new authentication
features.

**Files**: `pyproject.toml`, `CHANGELOG.md`.

**Subtasks**
1. Ensure `HttpClient` dependencies remain satisfied (no direct httpx
   additions) and introduce optional extras if needed for keyring/crypto.
2. Document the feature release in the changelog with highlights.
3. Bump version per release policy once features ship.

**Acceptance Criteria**
- Packaging checks stay green (`pip-audit`, `bandit`).
- Changelog entry summarizes GitHub OAuth work for end users.

---

# P0 — Security, Stability & Core UX

## P0.1 Secure token storage: permissions + optional encryption
**Goal**: Ensure `~/.pacx/config.json` is user-only readable and tokens can be encrypted with `PACX_CONFIG_ENCRYPTION_KEY`.
**Status**: ✅ Complete — implemented in `src/pacx/config.py` with regression coverage in `tests/test_config_security.py`.
**Files**: `src/pacx/config.py`, `docs/user-manual/08-config-profiles.md`, tests in `tests/test_config_security.py`.

**Subtasks**
1. **Verification**
   - Keep `_secure_path()` enforcing POSIX `0o600` and Windows best-effort ACLs; adjust if future OS quirks arise.
   - Monitor load-time permission warnings for false positives and tighten logging language if needed.
2. **Encryption maintenance**
   - Ensure Fernet/PBKDF2 support stays compatible with new dependencies; update docs if key handling changes.
   - Extend `EncryptedConfigError` messaging when new failure modes emerge.
3. **Docs & Tests**
   - Periodically review “Security & Encryption” guidance in `docs/user-manual/08-config-profiles.md` for accuracy.
   - Add new test cases to `tests/test_config_security.py` when regression scenarios are discovered.

**Acceptance Criteria**
- Regression tests in `tests/test_config_security.py` remain green.
- Documentation reflects current encryption and permission behavior.
- Any new edge cases are accompanied by targeted tests.

**Codex Prompt**
```text
Scope: Reference implementation for config security (already complete).

Review:
- src/pacx/config.py for `_secure_path()`, encryption helpers, and `EncryptedConfigError`.
- tests/test_config_security.py for coverage of permissions, encryption round-trips, and error handling.

Use this section to inform related follow-up work; no further changes required at this time.
```

---

## P0.2 CLI error handling: consistent, helpful messages
**Goal**: No raw tracebacks for expected operational errors; standardized Rich-formatted error output; exit code 1 on failure.
**Status**: ✅ Complete — `handle_cli_errors` decorator and messaging already live in `src/pacx/cli/common.py`.
**Files**: `src/pacx/cli/common.py`, `src/pacx/cli/*`, tests `tests/cli/`.

**Subtasks**
_None — milestone complete. Track future gaps here if new error types emerge._

**Acceptance Criteria**
- Newly added CLI commands or error paths continue to use `handle_cli_errors` so messaging stays aligned with existing output.
- Expand `tests/cli/test_errors.py` only when enhancing coverage for additional exceptions or debug scenarios.

**Codex Prompt**
```text
Scope: Reference existing `handle_cli_errors` implementation and extend messaging/tests only when new scenarios are discovered.

Review:
- src/pacx/cli/common.py for the shipped decorator and messaging.
- tests/cli/test_errors.py for baseline coverage.

Enhance:
- Add guidance for new exception types or debug affordances as needed.
- Ensure any new CLI command reuses the decorator.

Run toolchain when implementing enhancements.
```

---

## P0.3 Centralize config resolution in CLI
**Goal**: DRY helpers that resolve `environment_id` and `dataverse_host`, cached in Typer context.
**Status**: ✅ Complete — helpers live in `src/pacx/cli_utils.py` with coverage in `tests/test_cli_utils.py` and representative CLI flows.
**Files**: `src/pacx/cli_utils.py`, `src/pacx/cli/*`, tests `tests/test_cli_utils.py`, `tests/cli/`.

**Subtasks**
1. **Ongoing refactor audits** — When introducing new CLI commands, replace any bespoke config lookups with the shared helpers.
2. **Context caching review** — Expand helper docstrings/tests if multi-command sessions surface new caching expectations.
3. **Contributor guidance** — Document `pacx.cli_utils` usage patterns in CLI contributor docs to steer future implementations.

**Acceptance Criteria**
- `tests/test_cli_utils.py` (and related CLI coverage) continue to guard helper behavior as new scenarios are added.
- Contributor docs explicitly point CLI authors to the shared helpers, preventing drift.
- No new CLI command merges with redundant config resolution logic (verified during code review).

**Codex Prompt**
```text
Reference the shipped helpers in src/pacx/cli_utils.py when extending CLI behavior.

Audit new commands for redundant config resolution and update docs/tests alongside any helper refinements.

Run toolchain.
```

---

# P1 — Maintainability & Feature Parity

## P1.1 Modularize Solutions commands into subcommands
**Goal**: Replace single `solution --action <op>` with explicit subcommands:
`solution list|export|import|publish-all|pack|unpack|pack-sp|unpack-sp`.
**Files**: `src/pacx/cli/solution.py` (new) or split by op; `src/pacx/cli/__init__.py`; docs `docs/user-manual/07-solutions.md`; tests `tests/solution/`.

**Subtasks**
1. Create `cli/solution.py` Typer app with dedicated functions per op.
2. Keep backward-compatible alias (support `--action` path; print one-time deprecation warning).
3. Move logic out of monolithic function; keep signatures/output stable.
4. Update docs examples to subcommand style.
5. Tests: each subcommand, including `--wait` behavior and raw vs SP pack/unpack.

**Acceptance Criteria**
- `ppx solution <subcmd>` help is clear; old `--action` still works (with deprecation notice).
- All solution flows function and are tested.

**Codex Prompt**
```text
Refactor Solutions CLI into explicit subcommands with backward compatibility.

Edit:
- src/pacx/cli/__init__.py: add_typer(solution_app, name="solution").
- src/pacx/cli/solution.py: implement list/export/import/publish-all/pack/unpack/pack-sp/unpack-sp.
- Add shim handling `--action` -> call subcommands; warn once.

Docs: update 07-solutions.md examples.
Tests: tests/solution/test_solution_cli.py for each subcmd.

Run toolchain.
```

---

## P1.2 Finish Power Pages helpers cleanup
**Goal**: Single canonical path for webfile binary download and site upload strategies.
**Files**: `src/pacx/clients/power_pages*.py`, `src/pacx/power_pages/providers/*.py`, tests `tests/pages/`.

**Subtasks**
1. Ensure no duplicate `upload_site`/binary download functions exist; consolidate into client + provider layer.
2. Guarantee file naming safety (no traversal), deterministic output tree.
3. Tests: download with/without binaries; upload merge/replace; diff-permissions path.

**Acceptance Criteria**
- One implementation per concern; CLI calls client methods only.
- Tests cover flows and verify filesystem outputs.

**Codex Prompt**
```text
Unify Power Pages binary/transfer logic.

Search and remove duplicates; route through PowerPagesClient and providers.
Add tests for binary download, upload strategies, and permissions diff.

Run toolchain.
```

---

## P1.3 Implement `ppx connector delete`
**Goal**: Provide a first-class deletion command for custom connectors to avoid manual REST.
**Files**: `src/pacx/clients/connectors.py`, `src/pacx/cli/connectors.py`, docs `docs/user-manual/06-connectors.md`, tests `tests/connectors/`.

**Subtasks**
1. Client: add `delete_api(environment_id: str, name: str)` calling correct endpoint.
2. CLI: `ppx connector delete --environment-id <ENV> --name <NAME> --yes` (confirm unless `--yes`).
3. Docs: usage, warnings (irreversible), exit codes.
4. Tests: successful delete (mock), 404 returns friendly message.

**Acceptance Criteria**
- Command exists, documented, and tested.
- Follows error handling standards and config helpers.

**Codex Prompt**
```text
Add connector deletion support.

Client: implement delete_api().
CLI: new command ‘connector delete’ with confirmation flag.
Docs: update connectors guide.
Tests: deletion happy path + 404 case.

Run toolchain.
```

---

## P1.4 Docstrings & CLI help coverage
**Goal**: Ensure all public client methods and CLI commands have concise docstrings/help.
**Files**: `src/pacx/clients/*.py`, `src/pacx/cli/*.py`.

**Subtasks**
1. Add one-line docstrings + concise param/return notes where missing.
2. Review Typer option help; expand where ambiguous.
3. Verify `ppx --help` and `ppx <group> --help` are clear and complete.

**Acceptance Criteria**
- Docstring coverage ~100% for public surface.
- Help text is unambiguous.

**Codex Prompt**
```text
Add missing docstrings and improve CLI help.

Sweep clients and CLI modules; add concise docstrings and clearer option help.
Verify via help output.

Run toolchain.
```

---

# P2 — Documentation, CI/CD & Governance

## P2.1 Quick Start & walkthroughs (polish/extend)
**Goal**: A runnable mini-journey: install → profile → auth → first DV/connector/pages commands.
**Files**: `docs/user-manual/01-getting-started.md`, `docs/user-manual/03-cli-usage.md`.

**Subtasks**
1. Add sanitized example outputs and “what to expect” notes.
2. Cross-link to Authentication, Connectors, Solutions, Pages.
3. Add Troubleshooting (permissions, missing deps, timeouts, rate limits).

**Acceptance Criteria**
- New users can perform end-to-end flow with copy/paste commands.
- Screenshots or ASCII trees where helpful.

**Codex Prompt**
```text
Expand Quick Start with runnable end-to-end flow and troubleshooting.
Edit 01-getting-started.md, 03-cli-usage.md; add links and example outputs.
```

---

## P2.2 Flesh out feature docs: Connectors, Solutions, Pages
**Goal**: Complete, example-rich chapters for each major capability.
**Files**: `docs/user-manual/04-power-pages.md`, `docs/user-manual/06-connectors.md`, `docs/user-manual/07-solutions.md`.

**Subtasks**
1. Ensure each command has at least one example with flags and output.
2. Add limitations/notes (long-running ops, quotas, retry semantics).
3. Add “Verification” tips for each workflow.

**Acceptance Criteria**
- Docs are task-oriented and self-contained.
- No TODO placeholders remain.

**Codex Prompt**
```text
Finish feature docs with practical examples and notes.
Edit 04-power-pages.md, 06-connectors.md, 07-solutions.md accordingly.
```

---

## P2.3 CI hardening: static analysis, safety, coverage
**Goal**: Keep repo healthy by default.
**Files**: `.github/workflows/*.yml`, `pyproject.toml` (if needed).

**Subtasks**
1. Add `pip-audit` (or `uv pip audit`) step; fail on high severity CVEs.
2. Run `bandit -q -r src`; fail on high severity findings.
3. Enforce coverage floor (e.g., 85%) with `pytest --cov`.
4. Optional: Dependabot for Python and GitHub Actions updates.

**Acceptance Criteria**
- CI fails on critical security issues or coverage regression.
- Workflow documented in README/CONTRIBUTING.

**Codex Prompt**
```text
Harden CI with audit/bandit/coverage.
Edit .github/workflows/ci.yml; add steps; tune thresholds.
```

---

## P2.4 Governance: Agents.md, PR/Issue templates, Code of Conduct
**Goal**: Make contributing predictable and respectful.
**Files**: `AGENTS.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/*.md`, `CODE_OF_CONDUCT.md`.

**Subtasks**
1. Ensure Agents.md includes PR checklist, CI expectations, ADR pointers.
2. Add/refresh PR & Issue templates (bug, feature).
3. Ensure CoC present, linked from Agents.md and README.

**Acceptance Criteria**
- Templates render in GitHub UI.
- Agents.md reflects current workflow and expectations.

**Codex Prompt**
```text
Add/refresh governance docs and templates.
Edit AGENTS.md; create .github templates; link CoC.
```

---

# Validation & Release

## V.1 Smoke tests and golden outputs
**Goal**: Prevent accidental CLI regressions.

**Subtasks**
1. Add golden/snapshot tests for key commands (env list, dv whoami, connector list).
2. Normalize dynamic fields (timestamps/IDs) or snapshot with filters.

**Acceptance Criteria**
- Stable, reviewable text snapshots.
- Tests pass across OS runners.

**Codex Prompt**
```text
Add snapshot tests for key CLI commands with normalized outputs.
```

---

## V.2 Changelog & version bump
**Goal**: Document changes and cut a release.
**Files**: `CHANGELOG.md`, workflow that publishes to PyPI.

**Subtasks**
1. Update CHANGELOG with highlights (security, UX, docs, new delete command).
2. Bump version in `pyproject.toml`; tag release; ensure docs deploy.

**Acceptance Criteria**
- Release notes reflect real changes; package published; docs updated.

**Codex Prompt**
```text
Prepare release: update CHANGELOG, bump version, tag, verify publish & docs deploy.
```

---

# Sprint Checklist (Maintainers)

- [ ] P0.1 complete — config perms/encryption + docs + tests
- [ ] P0.2 complete — error handling decorator + tests
- [ ] P0.3 complete — config helpers + caching + tests
- [ ] P1.1 complete — solution subcommands + docs + tests (deprecate `--action`)
- [ ] P1.2 complete — power pages dedupe + tests
- [ ] P1.3 complete — connector delete + docs + tests
- [ ] P1.4 complete — docstrings & CLI help coverage
- [ ] P2.1–P2.4 complete — docs, CI, governance
- [ ] V.1–V.2 complete — snapshots + release

---

## How to Use These Prompts

For each task:
1. Open the repository in your coding agent.
2. Paste the **Codex Prompt** for that task.
3. Review the diff; iterate until **Acceptance Criteria** are met.
4. Commit with a Conventional Commit message.
5. Run the global validation commands and ensure everything is green.

