
# Agents Guide (for Code Agents)

## Objectives
- Maintain high test coverage (pytest + respx)
- Favor small, composable modules
- Keep public APIs typed (mypy passes)
- CLI flows must be covered by tests (Typer's CliRunner)

## Coding standards
- Black/ruff/mypy clean (CI enforces)
- Prefer dataclasses/pydantic models for payloads
- Use `HttpClient` for all HTTP calls; no direct httpx use
- Add docstrings & examples for public functions
- Mock external calls with `respx` in tests
- Keep the pytest suite free from warnings; upgrade or silence via `pytest.mark.filterwarnings` only with documented rationale.
- Treat any new pytest failure or warning as a blocking issue—fix the regression or add coverage in the same change.

## Style guides & best practices
- Favor explicit imports over wildcard imports to keep namespaces predictable.
- Keep functions under 30 lines by extracting helpers when logic grows complex.
- Use descriptive variable names; avoid abbreviations except for well-known terms (e.g., `id`, `url`).
- Document non-obvious business rules with inline comments adjacent to the logic.
- Prefer immutable data structures (tuples, frozensets) for constants and configuration.
- Ensure examples in documentation are runnable snippets that mirror unit tests when possible.

## TDD workflow
1. Write tests for the desired behavior.
2. Implement minimally to pass tests.
3. Refactor for clarity/performance.
4. Update docs under `docs/` and examples in README.

## Commit hygiene
- Conventional commits for features/fixes (feat:, fix:, docs:, refactor:, test:, ci:)
- Include rationale for API changes in ADRs (docs/adr)

## Pull Request Guidelines
- Ensure CI-critical tools pass locally before opening a PR: `ruff check`, `black --check`, `mypy`, `pytest --cov`, `pip-audit`, and `bandit`.
- Include tests for new features and bug fixes, and update existing tests or fixtures when behavior changes.
- Keep PRs focused and scoped; large refactors should be split or coordinated with maintainers via an ADR under `docs/adr/`.
- Reference related issues or ADRs directly in the PR description to provide reviewers context.
- Highlight any known limitations or follow-up work in the PR summary so maintainers can triage quickly.

### Pull Request Checklist
- [ ] Tests cover the change set and pass with coverage enforced (`pytest --cov`).
- [ ] Lint and type checks pass (`ruff check`, `black --check`, `mypy`).
- [ ] Security and dependency checks pass (`pip-audit`, `bandit`).
- [ ] Documentation is updated (README, `docs/`, and ADRs as needed).
- [ ] `CHANGELOG.md` includes an entry for user-visible changes.

Consult `docs/adr/` for the latest architectural decisions and review governance expectations in `PLAN.md`, `MAINTAINERS.md`, and `CODE_OF_CONDUCT.md` before proposing substantial changes.

## Code of Conduct
- All contributions must adhere to our [Code of Conduct](CODE_OF_CONDUCT.md); report incidents privately to the maintainers listed in `MAINTAINERS.md`.
- Foster inclusive discussions in issues, PRs, and review comments, especially when proposing significant architecture changes.
- When disagreements arise, default to documented decisions (ADRs, RFCs, or existing docs) and seek consensus respectfully.

## Branching
- feature/<short-desc>
- fix/<short-desc>
- docs/<short-desc>

## Release
- Tag `vX.Y.Z` to publish to PyPI (release workflow)
- Docs auto-deploy to GitHub Pages on push to main
