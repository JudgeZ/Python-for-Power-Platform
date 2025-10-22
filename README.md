
# PACX — PAC-like Python Library & CLI (Extended, TDD-ready)

This repository provides a test-driven, extensible Python library and CLI targeting Microsoft Power Platform + Dataverse.

## New in 0.2.0 (this build)
- **Profiles** and token storage (`ppx profile *`)
- **Auth** via MSAL device/client flows (`ppx auth device|client`) — optional extra
- **Retry/backoff** (429/5xx) in HTTP client
- **Dataverse CRUD** (`ppx dv {list,get,create,update,delete}`)
- **Solution zip/unzip** helpers (local pack/unpack of ZIP, not full SolutionPackager)

See `tests/` for TDD baselines and `openapi/` for the starter OpenAPI spec.

## New additions in v0.3.0
- Client credentials profile: `ppx auth client` (reads secret from env var you specify)
- Profile management: `ppx profile list|show|set-env|set-host`
- Dataverse CLI group: `ppx dv whoami|list|get|create|update|delete`
- Connectors push: `ppx connector push --environment-id ENV --name NAME --openapi openapi.yaml`
- Library: Dataverse CRUD helpers (`list_records/get_record/create_record/update_record/delete_record`)


## New in v0.5.0
- **Power Pages**: expanded tables (weblinksets, weblinks, redirects, webroles, entitypermissions, access rules) and `--tables core|full|<csv>`
- **$batch parsing**: per-op result parsing + `--report` in `ppx dv bulk-csv`
- **Secrets**: `ppx auth client` supports `--secret-backend` (`env|keyring|keyvault`), `--secret-ref`, and `--prompt-secret` for keyring
- **Docs**: C4 architecture diagrams (Mermaid) + full user manuals; docs workflow now builds Mermaid diagrams


## New in v0.6.0
- **Power Pages**: optional web file **binaries** export to `files_bin/` with checksums
- **CSV upsert**: **alternate-key** PATCH via `--key-columns`, configurable `--create-if-missing`
- **Upload strategies**: `replace|merge|skip-existing|create-only` for Pages
- **Docs**: Agents guide, Plan, ADRs, and repo governance docs
