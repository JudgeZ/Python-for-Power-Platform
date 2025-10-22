
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

## Branching
- feature/<short-desc>
- fix/<short-desc>
- docs/<short-desc>

## Release
- Tag `vX.Y.Z` to publish to PyPI (release workflow)
- Docs auto-deploy to GitHub Pages on push to main
