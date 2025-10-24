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

# P0 — Security, Stability & Core UX

## P0.1 Secure token storage: permissions + optional encryption
**Goal**: Ensure `~/.pacx/config.json` is user-only readable and tokens can be encrypted with `PACX_CONFIG_ENCRYPTION_KEY`.
**Files**: `src/pacx/config/*.py`, `docs/user-manual/08-config-profiles.md`, tests in `tests/config/`.

**Subtasks**
1. **Permissions**
   - On save, set POSIX mode `0o600` (Unix). On Windows, apply best-effort user-only ACL via `os.chmod` fallback.
   - On load, detect overly broad perms; auto-tighten and log a warning.
2. **Encryption**
   - Support `PACX_CONFIG_ENCRYPTION_KEY` (Fernet or PBKDF2-derived). Prefix encrypted fields with `enc:`.
   - On load, decrypt transparently; if key missing/wrong, raise `EncryptedConfigError` with recovery guidance.
3. **Docs & Tests**
   - Document key generation, storage, and “missing key” recovery behavior.
   - Tests: permission setting (skip/assert on Windows), encrypt/decrypt round-trip, error path when key absent.

**Acceptance Criteria**
- New configs are `0600` (POSIX); warning and fix if too open.
- Tokens encrypted when key present; friendly error when missing/wrong.
- Docs include clear “Security & Encryption” section.
- Tests cover permission + encryption paths.

**Codex Prompt**
```text
Scope: Harden config security and finalize encryption UX.

Edit:
- src/pacx/config/*.py: finalize _secure_path(), encrypt_field()/decrypt_field(), EncryptedConfigError.
- docs/user-manual/08-config-profiles.md: add ‘Security & Encryption’ with key generation & recovery.
- tests/config/test_config_security.py: permission + encryption round-trip + missing-key scenario.

Ensure: POSIX 0600; Windows best-effort; ‘enc:’ prefix; helpful errors.
Run: ruff/black/mypy/pytest.
```

---

## P0.2 CLI error handling: consistent, helpful messages
**Goal**: No raw tracebacks for expected operational errors; standardized Rich-formatted error output; exit code 1 on failure.
**Files**: `src/pacx/cli/common.py` (or helper), `src/pacx/cli/*`, tests `tests/cli/`.

**Subtasks**
1. Add decorator/helper to catch `HttpError`, auth/config errors, `EncryptedConfigError`.
2. Print `[red]Error:[/red] <summary>` with guidance (e.g., “Run `ppx auth device` …”).
3. Respect `--verbose` / `PACX_DEBUG=1` to enable tracebacks.
4. Tests for 500s, missing env/host, encrypted config without key; assert message text and exit code.

**Acceptance Criteria**
- Friendly errors across commands; `ppx doctor` references debug flag.
- Tests assert no traceback by default; traceback shown with `--verbose`/env.

**Codex Prompt**
```text
Implement unified CLI error handling.

Edit:
- src/pacx/cli/common.py: handle_cli_errors decorator (uses Rich).
- Wrap all command entrypoints with decorator.
- Respect PACX_DEBUG or --verbose to show tracebacks.

Tests:
- tests/cli/test_errors.py: HttpError 500, missing config, encrypted config without key.

Run toolchain.
```

---

## P0.3 Centralize config resolution in CLI
**Goal**: DRY helpers that resolve `environment_id` and `dataverse_host`, cached in Typer context.
**Files**: `src/pacx/cli/cli_utils.py` (new), `src/pacx/cli/*`, tests `tests/cli/`.

**Subtasks**
1. Implement `get_config_from_context(ctx)` to load once and cache.
2. Implement `resolve_environment_id_from_context(ctx, option)` and `resolve_dataverse_host_from_context(ctx, option)`.
3. Replace ad-hoc lookups in all commands.
4. Unit tests for helpers; one representative CLI test confirms unchanged behavior.

**Acceptance Criteria**
- Single config load per CLI invocation; consistent error messages.
- Tests pass; duplicate code removed.

**Codex Prompt**
```text
Create shared config helpers and apply to CLI commands.

New: src/pacx/cli/cli_utils.py with get_config_from_context(), resolve_* helpers.
Refactor CLI modules to use helpers.

Add tests: tests/cli/test_cli_utils.py + one command flow.

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

