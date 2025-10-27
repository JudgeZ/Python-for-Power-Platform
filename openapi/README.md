# Power Platform OpenAPI Bundle (r7)
Generated: 2025-10-26T21:00:36.157176

This bundle adds/updates endpoints requested for:
- Analytics (Advisor Recommendations)
- App Management (Applications) including environment-scoped listings, uninstall, and upgrade operation coverage
- Authorization (RBAC)
- Connectivity (Connectors)
- Environment Management (groups, ops, managed governance, settings, lifecycle provision/copy/reset/backup/restore)
- Governance (cross-tenant connection reports, rule-based policies)
- Licensing (billing policy, env associations, currency allocation/reports, environment billing policy, ISV contracts, storage warnings, temporary currency entitlement, tenant capacity details)
- Tenant settings (maker onboarding, feature controls, throttling policies)
- Power Apps (admin apps)
- Power Automate (cloud flows, flow actions, flow runs)
- Power Pages (websites lifecycle, WAF, scanning, IP allowlist, security/visibility)
- Power Virtual Agents (bots quarantine)
- User Management (apply admin role)

Security is modeled using OAuth2 implicit. RBAC read operations require the
`Authorization.RBAC.Read` scope, while create/update/delete flows require
`Authorization.RBAC.Manage` in addition to the tenant's `.default` scope.
Tenant-level configuration changes further require the `TenantSettings.Manage`
scope; read-only integrations can use `TenantSettings.Read`.
Where Microsoft Learn does not expose full object schemas, responses are typed as `object` with `additionalProperties: true` and will be refined with recorded schemas later.
Long-running operations include the `Operation-Location` response header when documented.
Environment lifecycle operations remain under the `2022-03-01-preview` API version and surface as long-running operations; the
Power Platform admin API throttling guidance applies (preview docs call out limits on concurrent environment copies and backup/
restore submissions per environment).

## Power Apps admin operations modeled here

- `GET /powerapps/environments/{environmentId}/apps/{appId}/versions`
  - Returns the set of available versions for a canvas app so tooling can surface roll-back choices.
- `POST .../{appId}:restore`
  - Accepts a `RestoreAppRequest` that names the source version and optional environment/app identifiers for cross-environment restores.
  - Returns `202 Accepted` with `Operation-Location` and `Retry-After` headers for polling.
- `POST .../{appId}:publish`
  - Publishes a specific app version using `PublishAppRequest.versionId` and follows the same async polling contract as restore.
- `GET .../{appId}/permissions`
  - Lists the principals and roles currently assigned to the app.
- `POST .../{appId}:share`
  - Grants access to users, groups, service principals, or tenant scopes using `ShareAppRequest.principals`.
- `POST .../{appId}:revokeShare`
  - Removes permissions for provided principal IDs.
- `POST .../{appId}:setOwner`
  - Transfers ownership to the supplied principal and can optionally demote the previous owner to co-owner.

> **Permissions:** All admin Power Apps operations require callers to be Global administrator, Power Platform administrator, or have the Power Platform service admin role in the tenant. Tenant-scoped app sharing also requires environment admin for the target environment.
