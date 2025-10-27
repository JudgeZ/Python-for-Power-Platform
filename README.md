
# Python for Power Platform

This repository provides a test-driven, extensible Python library and CLI targeting Microsoft Power Platform + Dataverse.

## Continuous Integration

We run automated quality gates on every push and pull request. Before opening a PR, ensure the following commands succeed locally:

1. `ruff check .`
2. `black --check .`
3. `mypy .`
4. `pytest --cov=pacx --cov-report=term-missing --cov-fail-under=85`
5. `pip-audit` (or `make security`)
6. `bandit -q -r src`

The CI workflow also uploads coverage artifacts from `pytest` and enforces a minimum 85% coverage floor, so new changes should keep or raise the overall coverage.

## New in 0.2.0 (this build)
- **Profiles** and token storage (`ppx profile *`)
- **Auth** via MSAL flows (`ppx auth create --flow device|web|client-credential`) — optional extra
- **Retry/backoff** (429/5xx) in HTTP client
- **Dataverse CRUD** (`ppx dv {list,get,create,update,delete}`)
- **Solution zip/unzip** helpers (local pack/unpack of ZIP, not full SolutionPackager)

See `tests/` for TDD baselines and `openapi/` for the starter OpenAPI spec.

## Custom connector API coverage

The `openapi/connectivity-connectors.yaml` document now includes custom connector CRUD, runtime status, and policy template endpoints. These APIs remain in preview and require callers to supply `api-version=2022-03-01-preview`. Service-side throttling currently enforces roughly 100 requests per minute per environment, so stagger long-running jobs or batch deployments accordingly. When acquiring Azure AD tokens for these operations, request the `Connectivity.CustomConnectors.Read.All`, `Connectivity.CustomConnectors.ReadWrite.All`, and `Connectivity.Policy.Read.All` scopes alongside the existing `.default` scope.

## Contributing

We welcome contributions from the community. Please review and abide by our [Code of Conduct](CODE_OF_CONDUCT.md) and the guidance captured in [`AGENTS.md`](AGENTS.md) before proposing changes. When opening pull requests or filing issues, use the repository templates to streamline collaboration:

- Pull requests use the [`PULL_REQUEST_TEMPLATE`](.github/PULL_REQUEST_TEMPLATE.md), which includes the required test, lint/type check, documentation, and changelog checklist.
- Bug reports and enhancement ideas start with the issue templates under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/), which reference the same governance resources (ADRs, PLAN, MAINTAINERS) to keep discussions grounded in documented decisions.

For larger changes, consult the existing [ADRs](docs/adr/) and governance policies in [PLAN.md](PLAN.md) and [MAINTAINERS.md](MAINTAINERS.md) to understand current direction and decision-making processes.

## New additions in v0.3.0
- Client credentials profile: `ppx auth create --flow client-credential` (reads secret from env var you specify)
- Profile management: `ppx profile list|show|set-env|set-host`
- Dataverse CLI group: `ppx dv whoami|list|get|create|update|delete`
- Connectors push: `ppx connector push --environment-id ENV --name NAME --openapi openapi.yaml`
- Library: Dataverse CRUD helpers (`list_records/get_record/create_record/update_record/delete_record`)


## New in v0.5.0
- **Power Pages**: expanded tables (weblinksets, weblinks, redirects, webroles, entitypermissions, access rules) and `--tables core|full|<csv>`
- **$batch parsing**: per-op result parsing + `--report` in `ppx dv bulk-csv`
- **Secrets**: `ppx auth create --flow client-credential` supports `--secret-backend` (`env|keyring|keyvault`), `--secret-ref`, and `--prompt-secret` for keyring
- **Docs**: C4 architecture diagrams (Mermaid) + full user manuals; docs workflow now builds Mermaid diagrams


## New in v0.6.0
- **Power Pages**: optional web file **binaries** export to `files_bin/` with checksums
- **CSV upsert**: **alternate-key** PATCH via `--key-columns`, configurable `--create-if-missing`
- **Upload strategies**: `replace|merge|skip-existing|create-only` for Pages
- **Docs**: Agents guide, Plan, ADRs, and repo governance docs

## New in v0.7.0
- **Binary providers**: `ppx pages download` supports `--binary-provider annotations|azure` with provider manifests & checksums.
- **Permissions diffing**: `ppx pages diff-permissions` builds create/update/delete plans comparing local exports vs Dataverse.
- **Natural key upsert**: Pages uploads honor default/override key sets; manifest captures defaults for reuse.
- **Batch resiliency**: `$batch` retries (429/5xx) with aggregated stats surfaced in `ppx dv bulk-csv` output.
- **Solution parity**: `solution_sp` pack/unpack mirrors SolutionPackager folder mapping across component types.
- **Operational tooling**: `ppx doctor` validates environment + Dataverse access; GitHub Actions `publish.yml` drives TestPyPI/PyPI releases.
