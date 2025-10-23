# PLAN.md — Automation-Ready Implementation Plan

This plan converts the prior repository review into **actionable, copy/paste-ready prompts** for a code-generation assistant (“Codex/agent”).  
Each task includes: a clear goal, rationale, acceptance criteria, and a **well-scoped prompt** that tells the agent exactly what to change, where, and how to validate.

> **Scope:** Repository “JudgeZ/Python-for-Power-Platform”.  
> **Primary language:** Python 3.10+ (Typer, httpx, Pydantic).  
> **CLI entry:** `src/pacx/cli.py` (to be modularized).  
> **Docs site:** `docs/` (MkDocs).  
> **Config:** `src/pacx/config/*.py` (may include ConfigStore).

---

## Conventions for All Prompts

- **Safety & consistency**
  - Do not remove public APIs or change semantics without explicit justification.
  - Prefer small, focused commits; preserve history; keep changes localized.
  - Keep retries, auth, and HTTP error handling centralized via the existing `HttpClient` / shared utilities.
- **Style & tooling**
  - Run: `ruff --fix . && black . && mypy .` and ensure no new warnings.
  - Tests must pass: `pytest -q` (add/adjust tests as needed).
  - Follow existing patterns (dataclasses/Pydantic; Typer for CLI; Rich for output).
- **Docs**
  - When adding or changing behavior surfaced in CLI, update relevant docs and `--help` text.
- **Commits**
  - Use Conventional Commit prefixes (e.g., `feat:`, `fix:`, `docs:`, `refactor:`).

---

# Priority Roadmap

- **P0 (Security & Stability):**
  1. ✅ Secure token storage permissions (and optional encryption).
  2. ✅ Improve CLI error handling (friendly messages, consistent exits).
  3. ✅ Centralize repeated CLI config resolution logic.

- **P1 (Maintainability):**
  4. Modularize `cli.py` into subcommand modules.
  5. Clean up duplicate/mis-scoped functions (Power Pages helpers, etc.).
  6. Add/complete docstrings & help text.

- **P2 (Adoption & Docs):**
  7. Expand “Quick Start” and walkthroughs.
  8. Flesh out feature docs (Connectors, Solutions).
  9. Sync tests with current CLI & behaviors.
  10. Update `Agents.md` with PR review & Code of Conduct notes.

---

## 1) Secure Token Storage (permissions + optional encryption)

**Goal**: Restrict `config.json` to user-only access and optionally encrypt sensitive token fields.  
**Rationale**: Tokens in plaintext in a world-readable file are a risk; permissions + optional encryption mitigate it.  
**Acceptance**:
- `config.json` written with `0600` (Unix) or user-only ACL (Windows).
- Optional encryption gate (env-var key or passphrase) to encrypt token fields.
- Clear docs + warnings if permissions are too open.
- Tests covering permission setting; encryption path smoke-tested.

**Prompt (copy/paste to agent):**
```text
Act as a senior Python engineer. Implement secure token storage for the PACX config.

Repository context:
- Config store lives under `src/pacx/config/` (e.g., ConfigStore). Tokens may be persisted in `~/.pacx/config.json`.
- Cross-platform support (Linux/macOS/Windows).

Tasks:
1) File permissions
   - After writing `config.json`, set restrictive permissions:
     - Unix: `chmod 0o600` on the file (owner read/write only).
     - Windows: apply user-only ACL (use `os.chmod` to remove group/other bits; if needed, wrap in platform guard and document limitations).
   - On startup or after save, verify permissions; if too open, fix them and log a warning.

2) Optional encryption
   - Add optional encryption of sensitive fields (e.g., access/refresh tokens) controlled by env var `PACX_CONFIG_ENCRYPTION_KEY` or a CLI flag.
   - Use `cryptography` Fernet if available; fail open (plaintext) if key absent, but emit a one-line notice in verbose mode.
   - Keep rest of config plaintext for diffability; only wrap sensitive fields.
   - Provide small helper `encrypt_field()/decrypt_field()` and integrate in load/save paths.
   - Add unit tests: permission setting (skip or adapt on Windows CI), encryption round-trip (encrypt->persist->load->decrypt).

3) Documentation
   - Update docs (`docs/user-manual/01-getting-started.md` or a new “Security” page): explain permissions, optional encryption, how to set `PACX_CONFIG_ENCRYPTION_KEY`, and trade-offs.

Validation:
- Run `ruff --fix . && black . && mypy . && pytest -q`.
- Manually inspect file permissions locally (best-effort on CI).
```
---

## 2) Improve CLI Error Handling (friendly messages)

**Goal**: Replace raw tracebacks with concise, actionable error messages; standardize exit codes.  
**Rationale**: Better UX for operational CLI; errors should guide the user.  
**Acceptance**:
- Known errors (`HttpError`, auth/config errors) are caught and displayed with Rich-formatted messages.
- Exit with code `1` on failures; no tracebacks for expected errors.
- Tests cover error messaging + exit codes.

**Prompt:**
```text
Enhance CLI error handling for PACX.

Scope:
- Commands in `src/pacx/cli.py` (and, after modularization, in submodules).

Requirements:
- Wrap command bodies to catch:
  - `HttpError` (include status + concise message response snippet).
  - Auth errors (e.g., MSAL) -> suggest re-auth (`ppx auth device` / `ppx auth secret`).
  - Missing config (use `typer.BadParameter` with actionable guidance).
- Print user-friendly message using Rich (prefix with “[red]Error:[/red]”).
- Exit via `raise typer.Exit(1)` for failure paths.
- Do not print stack traces for expected operational errors; keep debug logging behind a `--verbose` or `PACX_DEBUG` flag.
- Standardize messages across commands.

Tests:
- Add CLI tests using `CliRunner` that simulate:
  - 500 `HttpError` (mock httpx) -> message + exit code 1.
  - Missing env/host -> helpful `BadParameter` guidance.
  - Auth failure -> clear suggestion to re-auth.

Run formatters, type checks, and tests.
```
---

## 3) Centralize CLI Config Resolution Logic

**Status:** ✅ Completed – Typer contexts now memoise configuration data and expose context-aware helpers so commands no longer reload profiles on every invocation.

**Summary:**
- Added `get_config_from_context`, `resolve_environment_id_from_context`, and `resolve_dataverse_host_from_context` helpers that cache `ConfigData` on the Typer context.
- Updated CLI commands to reuse these helpers, eliminating repeated calls to `ConfigStore().load()` and ensuring consistent config resolution.
- Extended unit coverage in `tests/test_cli_utils.py` to exercise the new helpers and confirm caching behaviour.

**Next focus:** Continue with P1 maintainability work (CLI modularisation) now that shared context helpers are in place.

---

## 3) Centralize CLI Config Resolution

**Goal**: DRY helper(s) to resolve `environment_id`, `dataverse_host`, etc.  
**Rationale**: Many commands reimplement the same config lookup; centralizing improves consistency.  
**Acceptance**:
- Helpers created (`src/pacx/cli_utils.py` or similar).
- All commands call into helpers; duplicate logic removed.
- Tests for helpers and one or two representative commands.

**Prompt:**
```text
Create shared CLI config-resolution helpers and apply them across commands.

Steps:
1) New module `src/pacx/cli_utils.py` with functions:
   - `resolve_environment_id(opt: str|None) -> str`
   - `resolve_dataverse_host(opt: str|None) -> str`
   - Each loads config once (ConfigStore), prefers explicit option, falls back to default; otherwise raises `typer.BadParameter` with advice to run `ppx profile set-env` / set host.
2) Replace ad-hoc resolution in CLI commands with these helpers.
3) Tests:
   - Unit tests for helpers (configured default vs. missing).
   - One CLI command test to ensure behavior unchanged (success and error cases).

Run lint/type/tests.
```
---

## 4) Modularize `cli.py` into Subcommand Modules

**Goal**: Split large CLI into `cli_auth.py`, `cli_profile.py`, `cli_dv.py`, `cli_connector.py`, `cli_pages.py`, etc.  
**Rationale**: Smaller files by domain improve readability and reduce merge conflicts.  
**Acceptance**:
- `src/pacx/cli.py` becomes a thin orchestrator.
- Sub-apps moved with identical behavior + help text.
- Tests unaffected (or minimally updated).

**Prompt:**
```text
Modularize the Typer CLI.

Actions:
1) Create modules:
   - `src/pacx/cli_auth.py` (auth-related commands)
   - `src/pacx/cli_profile.py`
   - `src/pacx/cli_dv.py` (Dataverse)
   - `src/pacx/cli_connector.py`
   - `src/pacx/cli_pages.py` (Power Pages)
2) Move each sub-app’s commands verbatim, preserving decorators, options, and help.
3) In `src/pacx/cli.py`, keep `app = typer.Typer(...)` and `add_typer(...)` per sub-app.
4) Ensure shared utilities (`cli_utils`) are imported where needed.
5) Verify `ppx --help` and subcommand `--help` display as before.

Run tests and linting.
```
---

## 5) Clean Up Duplicate / Mis‑Scoped Functions (Power Pages)

**Goal**: Unify Power Pages helpers (e.g., binary download, upload flows) into a single canonical implementation with proper scope.  
**Rationale**: Duplicated or misplaced functions cause drift and bugs.  
**Acceptance**:
- Single, well-scoped implementation for webfile binary download.
- One `upload_site` path used throughout.
- Tests updated/added for these flows.

**Prompt:**
```text
Refactor Power Pages helpers to remove duplication.

Scope:
- `src/pacx/clients/power_pages*.py` and any related provider/helpers modules.

Tasks:
- If a `download_webfile_binaries` free function exists, convert it to:
  - a private method on `PowerPagesClient` **or**
  - a single provider helper used by the client (choose the pattern already dominant).
- Ensure `upload_site` is uniquely implemented and all callers route through it; remove stale/duplicate variants.
- Keep unit tests green; add a focused test that exercises webfile binary download to a temp directory and verifies expected files are created (mock remote).

Run formatters, type checks, and tests.
```
---

## 6) Add/Improve Docstrings & CLI Help Text

**Goal**: Ensure all public methods/classes have docstrings; CLI commands have helpful `--help` text.  
**Rationale**: Improves maintainability and user discoverability.  
**Acceptance**:
- Docstrings added where missing, especially in `clients/` and `models/`.
- CLI commands show clear descriptions and option help.
- No functional changes.

**Prompt:**
```text
Add missing docstrings and refine CLI help text.

Tasks:
- For `src/pacx/clients/*.py`, ensure public methods (e.g., Dataverse, Connectors, Power Pages) have concise docstrings (purpose, key params/returns).
- For CLI commands, add/expand function docstrings (Typer shows these in `--help`).
- Improve option help where vague (e.g., clarify `--openapi` path semantics).

Verify with `ppx <group> --help` and `ruff/mypy`.
```
---

## 7) Expand “Quick Start” & Walkthroughs

**Goal**: Add a hands-on Quick Start that gets users from install → profile → auth → first command.  
**Rationale**: Current docs are light; examples accelerate adoption.  
**Acceptance**:
- New/updated “Getting Started” page with runnable examples and expected outputs.
- Coverage for auth flows and basic DV/connector operations.

**Prompt:**
```text
Author a Quick Start in docs.

Where:
- `docs/user-manual/01-getting-started.md` (or create if missing).

Include:
- Installation (pip install; optional extras).
- Create profile; set default env/host.
- Authenticate via device code and via client secret (both paths).
- Run first commands: `ppx env`, `ppx dv whoami`, `ppx connector list`.
- Show example outputs (anonymized).

Ensure cross-links to deeper docs (Connectors, Solutions).
```
---

## 8) Flesh Out Feature Docs (Connectors, Solutions)

**Goal**: Complete guides for Custom Connectors and Solutions.  
**Rationale**: Stubs exist; users need end‑to‑end guidance.  
**Acceptance**:
- Connectors page explains list/push/update with examples.
- Solutions page covers list/export/import and pack/unpack (if supported).
- Screenshots or example outputs where helpful.

**Prompt:**
```text
Complete docs for Connectors and Solutions.

Connectors (`docs/user-manual/06-connectors.md`):
- Intro: What are custom connectors, when to use PACX.
- Commands: list, push (from OpenAPI), get/delete if available.
- Examples: CLI invocations + outputs; common pitfalls.

Solutions (e.g., `docs/user-manual/05-solutions.md`):
- Intro: Dataverse Solutions overview.
- Commands: list, export (managed/unmanaged), import (notes on async), unpack/pack from source (if implemented).
- Examples: real command lines; file layout after unpack.

Add navigation links; run MkDocs locally if configured.
```
---

## 9) Sync Tests with Current CLI & Logic

**Goal**: Update tests to reflect latest CLI flags, messages, and flows; add tests for new features.  
**Rationale**: Tests are the guardrail; they must match reality.  
**Acceptance**:
- Existing tests updated for new error messages/flows.
- New tests for Pages, Solutions pack/unpack, retries where applicable.
- `pytest -q` green locally and in CI.

**Prompt:**
```text
Align and extend the test suite.

Tasks:
- Review CLI tests (use `CliRunner`) and update for current flags and messages (e.g., standardized error prefix, new helpers).
- Add tests for new pages flows (binary download), `doctor` command if present, and solution pack/unpack (fixture zip or minimal fake).
- Add a retry test for transient HTTP (mock 429/5xx with respx).

Ensure tests are deterministic and pass on CI.
```
---

## 10) Update `Agents.md` (PR Review & Code of Conduct)

**Goal**: Equip contributors/agents with explicit PR process and community standards.  
**Rationale**: The guide is strong but missing PR review steps & CoC callout.  
**Acceptance**:
- New “Pull Request Guidelines” section.
- New “Code of Conduct” reminder (link to `CODE_OF_CONDUCT.md` if present).

**Prompt:**
```text
Amend `Agents.md` with collaboration guidelines.

Add sections:
1) Pull Request Guidelines
   - PRs required for non-trivial changes; no direct pushes to main.
   - Use Conventional Commits; link issues; summarize change and risks.
   - Run lint/type/tests before review; note in the PR.
   - Be responsive and respectful in review; squash/merge per repo policy.

2) Code of Conduct
   - State adherence to the project CoC; link to `CODE_OF_CONDUCT.md` (or add one if missing).
   - Emphasize respectful, inclusive communication; zero tolerance for harassment.

No code changes; doc only.
```
---

## Validation Checklist (for Maintainers)

- [ ] All P0 tasks merged; security & UX improved.
- [ ] CLI still backward compatible (no accidental API breaks).
- [ ] Docs site builds without warnings; new pages linked in nav.
- [ ] CI green: lint, type, tests.
- [ ] Release notes updated (if user-facing behavior changed).
- [ ] `Agents.md` reflects latest workflow and standards.

---

**How to use this plan**  
Work from **P0 → P1 → P2**. For each task, paste the corresponding prompt into your coding agent with the repo opened. Review diffs, run checks locally, and iterate until the acceptance criteria are met.
