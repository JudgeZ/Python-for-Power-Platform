
# PACX Work Plan & Improvement Backlog

## Ready
- Power Pages: binary extraction for web files (annotation-based) ✅
- Alternate-key upserts in CSV bulk pipeline ✅
- Pages upload strategies: replace|merge|skip-existing|create-only ✅
- $batch per-op parsing + CLI reporting ✅
- Secrets backends: env|keyring|KeyVault CLI flags ✅
- C4 architecture diagrams & user manuals ✅

## Next Up (Proposals)
- Web file content export via configurable providers (annotations/notes, Azure Blob virtual files) with manifest.json
- Create provider protocol under `pacx/power_pages/providers.py` to orchestrate binary exporters and have `PowerPagesClient.download_site` return provider summaries alongside export paths.
- Move annotation download logic into a default provider, add CLI wiring for provider selection, and guard `include_files` usage.
- Implement Azure Blob virtual file provider with credential handling plus a manifest capturing checksums and provider results.
- Extend `tests/test_power_pages_binary.py` and documentation to validate provider selection, manifests, and CLI instructions.
- Batch response *error* aggregator and automated retry for transient failures
- Detect per-operation 429/5xx responses in `send_batch`, regroup, and retry with exponential backoff distinct from transport retries.
- Aggregate success/failure stats in `bulk_csv_upsert`, surfacing retry counts and grouped errors to CLI reporters.
- Cover retry and aggregation paths with new tests in `tests/test_bulk_csv.py` and `tests/test_batch_parse.py` using `respx` mocks.
- Document retry semantics and new reporting fields in README/docs for operator awareness.
- Natural-key upsert for Pages entities (config-driven key sets)
- Map preferred natural keys per entity and use them in `PowerPagesClient.upload_site` via `build_alternate_key_segment` when IDs are absent.
- Allow CLI/manifest overrides for key configuration and ensure `pages upload` passes these settings through.
- Add tests under `tests/test_power_pages.py` for ID-less updates covering merge/create-only strategies.
- Document default key sets and customization guidance.
- Power Pages permissions model diffing & sync planning
- Add `pages diff-permissions` CLI command to load local exports and Dataverse data for comparison.
- Build diff engine grouping differences by entity type and emitting actionable plans (create/update/delete).
- Test diff logic with fixture JSON under `tests/` and validate CLI output formatting.
- Document diff workflow and consumption guidance.
- SolutionPackager parity: full mapping for all solution components
- Expand `unpack_to_source` to cover remaining solution ZIP structures and map them deterministically.
- Mirror the mapping in `pack_from_source` to ensure round-tripping parity across components.
- Extend `tests/test_solution_zip.py` with fixtures validating parity for new component types.
- Update documentation/ADR summarizing mapping coverage and exceptions.
- GitHub Actions: matrix publish to TestPyPI & PyPI on manual approval
- Add `.github/workflows/publish.yml` with `workflow_dispatch`, single build job, and matrix deploy to TestPyPI/PyPI using cached artifacts.
- Introduce approval gate before PyPI deployment (environment protection or approval job).
- Cache build artifacts between jobs and verify integrity prior to upload.
- Document workflow usage in README/CONTRIBUTING.
- `ppx doctor` command to validate environment, scopes, and profile
- Implement Typer subcommand performing profile, environment variable, token, and Dataverse connectivity checks with remediation hints.
- Provide exit codes suitable for CI and reuse existing helper functions for HTTP probing.
- Add CLI tests using `CliRunner` and `respx` for healthy/missing-profile/token failure scenarios.
- Document command behavior, sample output, and support integration.

## Stretch
- Async http client variants for high-volume bulk operations
- CSV schema inference and column mapping hints
- Pluggable secrets backend interface with additional providers
