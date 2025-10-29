# Project Plan — PACX (Oct 29, 2025)

Summary
- Focus: ALM excellence, developer productivity, governance at scale.
- Themes: solution intelligence, environment operations, Power Automate bulk ops, Canvas app lifecycle, plugin/PCF support, DLP impact, audit/reporting.
- Quick wins: expose and extend already-implemented groups; add missing CLI wiring; deepen Dataverse + solution ops.

Parallel Agent Results: Themes
- Common priorities: Solution intelligence (deps/health), environment lifecycle operations with wait/status, Power Automate bulk state/ownership, Canvas app pack/unpack, plugin/PCF basics, DLP impact, audit/reporting.
- Repository strengths leveraged: `src/pacx/clients/*`, `src/pacx/cli/*`, shared `HttpClient`, tests via `respx` + `CliRunner`, coverage ≥ 85%.

Final Roadmap

Phase 1 — Fast Wins and Foundations
- Expose hidden CLI groups
  - Ensure main `ppx` exposes `power_automate` and `environment` (modules already in `src/pacx/cli/`).
  - Tests: `tests/cli/test_cli_entrypoint_exposes_groups.py` using `CliRunner`.
- Solution import/export options
  - Add flags: `--activate-plugins`, `--publish-workflows`, `--overwrite-unmanaged`, `--include-dep`/

Status
- [x] Old plans removed: done
- [x] CLI groups exposed (power_automate, environment): done (wired in src/pacx/cli/__init__.py)
- [x] Docs plan page removed and nav updated: done
- [x] Phase 1.A Dataverse CRUD/query CLI + tests: done
- [x] Phase 1.B Solution import/export flags + tests: done
- [x] Phase 2.A Solution intelligence (deps/components/check): done
- [x] Phase 2.B Environment wait/status (OperationMonitor + --wait/--timeout): done
- [x] Phase 2.C Connection references (list/validate): done
- [x] Phase 3 — DLP & Policy Management: done
- [x] Phase 4 — Flow deployment automation: done
- [x] Phase 5 — Environment & Solution CI/CD helpers: done
- [x] Phase 6 — Audit & compliance reporting: done
- [x] Phase 7 — CoE CLI + tests: done
- [ ] Phase 7 — CoE client implementation + docs: planned

Phase 3 — DLP & Policy Management
- Goals
  - Manage DLP policies (list/get/create/update/delete) with scope enforcement.
  - Update connector classifications and manage policy assignments.
  - Support governance assignments and validate connection reference health for DLP impact.
- Commands
  - `ppx policy dlp list|get|create|update|delete`
  - `ppx policy dlp connectors list|update`
  - `ppx policy dlp assignments assign|remove|list`
  - `ppx governance assignment create|list`
  - `ppx connection list|validate`
- Acceptance (tests)
  - `tests/test_cli_policy.py` (list output, create waits, connectors update payload, assignments wait, scope requirement errors)
  - `tests/test_cli_governance.py` (assignment list/create and single-target validation; report submit with polling)
  - `tests/cli/test_cli_connections.py` (list JSON; validate flags missing connection as invalid)


Phase 4 — Flow Deployment Automation
- Goals
  - Operate on cloud flows: list/get/update state/delete with confirmation.
  - Trigger runs; list/get/cancel runs and retrieve diagnostics.
- Commands
  - `ppx flows list|get|set-state|delete`
  - `ppx power flows get|update|delete|run`
  - `ppx power runs list|get|cancel|diagnostics`
- Acceptance (tests)
  - `tests/cli/test_cli_power_automate.py` (list, case-normalized set-state, delete with --yes)
  - `tests/test_cli_power_platform_commands.py` (flows get/update/delete; run; runs list/get/cancel/diagnostics)


Phase 5 — Environment & Solution CI/CD Helpers
- Goals
  - Environment lifecycle operations with wait/timeout; environment group management and application to environments.
  - App admin lifecycle actions (versions, restore, publish, share/revoke, permissions, ownership).
  - Solution export/import with flags; pack/unpack (standard and SP source).
  - Dataverse CRUD and bulk utilities supporting pipelines.
- Commands
  - `ppx environment list|show|create|delete|copy|reset|backup|restore --wait --timeout`
  - `ppx environment groups list|show|create|update|delete|add|remove`
  - `ppx env-group apply`
  - `ppx apps versions|restore|publish|share|revoke-share|permissions|set-owner`
  - `ppx solution list|deps|components|check|export|import|publish-all|pack|unpack|pack-sp|unpack-sp`
  - `ppx dv whoami|list|get|create|update|delete|bulk-csv`
- Acceptance (tests)
  - `tests/cli/test_cli_environment_ops.py` (copy/backup wait + timeout handling)
  - `tests/cli/test_cli_app_admin.py` (admin list/share/revoke; env groups CRUD; ops)
  - `tests/test_cli_power_platform_commands.py` (env copy; env-group apply; apps versions/restore/publish/share/revoke/permissions/set-owner)
  - `tests/cli/test_cli_solution_flags.py` and `tests/test_cli_solutions.py` (export/import flags; publish-all; pack/unpack variants)
  - `tests/cli/test_cli_dataverse_crud.py` (CRUD/query happy/404 paths)


Phase 6 — Audit Logs & Compliance Reporting
- Goals
  - Advisor analytics: list scenarios/actions/resources/recommendations; show/status; acknowledge/dismiss (wait by default); execute actions.
  - Governance reporting: submit cross-tenant connection reports with optional polling; status/list retrieval.
- Commands
  - `ppx analytics scenarios|actions|resources|recommendations|show|status|acknowledge|dismiss|execute`
  - `ppx governance report submit --poll|status|list`
- Acceptance (tests)
  - `tests/test_cli_analytics_commands.py` (scenarios; acknowledge with/without wait; execute parameter serialization)
  - `tests/test_cli_governance.py` (report submit with polling)


Phase 7 — CoE Starter Kit Integration
- Goals
  - Integrate CoE insights: inventory (apps/flows/makers), baseline metrics export, and optional sync to Dataverse/CSV.
- Commands
  - `ppx coe inventory|metrics|makers`
  - `ppx coe export --format json|csv --out <path>`
- Acceptance (tests)
  - `tests/cli/test_cli_coe_commands.py` (inventory JSON with value, makers filter by env, metrics JSON, export json/csv formatting)
