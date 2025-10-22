
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
- Batch response *error* aggregator and automated retry for transient failures
- Natural-key upsert for Pages entities (config-driven key sets)
- Power Pages permissions model diffing & sync planning
- SolutionPackager parity: full mapping for all solution components
- GitHub Actions: matrix publish to TestPyPI & PyPI on manual approval
- `ppx doctor` command to validate environment, scopes, and profile

## Stretch
- Async http client variants for high-volume bulk operations
- CSV schema inference and column mapping hints
- Pluggable secrets backend interface with additional providers
