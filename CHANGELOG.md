# Changelog

## Unreleased

- Add licensing client and CLI coverage for billing policies, allocations, storage warnings,
  and capacity snapshots with documentation for required scopes.
- Extend Analytics advisor recommendations OpenAPI with detail, acknowledgement, dismissal, and status polling endpoints, plus documentation covering the end-to-end workflow.
- Add Advisor Recommendations analytics client and CLI commands with async polling support and documented scopes.
- Add a Power Pages admin client with CLI support for website lifecycle, WAF, scan, and visibility operations.
- Add governance client and CLI coverage for cross-tenant connection reports and rule-based policy assignments.
- Add Power Virtual Agents bot client helpers and `pacx pva` CLI commands covering bot publication, packages, channels, and quarantine flows.
- Fix polling utilities to raise `TimeoutError` and surface failures in `ppx solution import --wait`.
- Remove the 50-note pagination limit in Power Pages annotation exports by following `@odata.nextLink` pointers across pages.
- Harden solution archive extraction, including SolutionPackager layouts, against Zip Slip directory traversal.
- Ensure Azure Blob binary downloads append SAS tokens even when URLs contain query strings.
- Expose lifecycle management on HTTP-based clients to close connections when finished.
- Include `respx` in the default dependency set so local pytest runs have the required mock tooling.
- Allow Dataverse hosts passed to `DataverseClient` and CLI commands to include the scheme or bare hostname interchangeably.
- Introduce `ppx auth create` for device, web, and client-credential flows while keeping legacy aliases with deprecation warnings.
- Extend `openapi/connectivity-connectors.yaml` with custom connector CRUD, validation, policy template, and runtime status endpoints plus supporting schemas.
- Extend the User Management OpenAPI with admin role audit/rollback endpoints, detailed role assignment schemas, and async operation tracking models, with README guidance for integrators.
- Extend the RBAC OpenAPI spec with role definition CRUD endpoints, modeled
  schemas, and explicit `Authorization.RBAC.*` scope requirements.
- Add Authorization RBAC client, CLI (`ppx auth roles|assignments`) commands,
  and coverage verifying OAuth scope documentation.
- Model Power Apps admin versioning, restore/publish, and sharing ownership APIs in the OpenAPI bundle for SDK generation.
- Expand the Power Automate OpenAPI surface with flow lifecycle, run management, and diagnostics endpoints.
- Expand the Power Virtual Agents bots OpenAPI document with bot metadata, publish/unpublish, package import/export, and channel configuration endpoints.
- Extend the Dataverse solution OpenAPI definitions with clone, stage, publish-all, managed export, and translation lifecycle actions plus typed payloads.
- Introduce a DLP policy client and CLI commands covering CRUD, connector grouping, and environment assignments with async polling helpers and scope validation.
- Add tenant settings client and CLI commands covering feature controls, update payloads, and access request workflows with permission guidance.
- Add user management client APIs and `ppx users admin-role` commands with polling-aware CLI UX and role/scope documentation.
- Add Dataverse client helpers and models for staging upgrades, cloning patches, solution export variants, translation flows, and delete/promote actions, including LRO metadata exposure and documentation updates.

- 0.2.0 Extended features
