# Power Platform OpenAPI Bundle (r7)
Generated: 2025-10-26T21:00:36.157176

This bundle adds/updates endpoints requested for:
- Analytics (Advisor Recommendations)
- App Management (Applications) including environment-scoped listings, uninstall, and upgrade operation coverage
- Authorization (RBAC)
- Connectivity (Connectors)
- Environment Management (groups, ops, managed governance, settings)
- Governance (cross-tenant connection reports, rule-based policies)
- Licensing (billing policy, env associations, currency allocation/reports, environment billing policy, ISV contracts, storage warnings, temporary currency entitlement, tenant capacity details)
- Power Apps (admin apps)
- Power Automate (cloud flows, flow actions, flow runs)
- Power Pages (websites lifecycle, WAF, scanning, IP allowlist, security/visibility)
- Power Virtual Agents (bots quarantine)
- User Management (apply admin role)

Security is modeled using OAuth2 implicit with `.default` scope.
Where Microsoft Learn does not expose full object schemas, responses are typed as `object` with `additionalProperties: true` and will be refined with recorded schemas later.
Long-running operations include the `Operation-Location` response header when documented.
