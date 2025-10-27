# Licensing APIs

PACX includes a typed client and CLI helpers for the Power Platform licensing APIs. These
endpoints cover billing policies, environment associations, ISV contracts, currency
allocations, storage warnings, and tenant capacity reporting. All calls require an Azure AD
token scoped for the Power Platform resource:

```
https://api.powerplatform.com/.default
```

## Python client

Use :class:`pacx.clients.licensing.LicensingClient` to issue requests. The client exposes
methods mirroring the official REST operations in ``openapi/licensing.yaml`` including:

- Billing policy CRUD and provisioning refresh operations.
- Environment association helpers and environment policy lookups.
- Currency allocation management, including tenant-wide currency reports.
- ISV contract CRUD helpers.
- Storage warning lookups by category or entity.
- Capacity endpoints for tenant snapshots, environment allocations, and temporary
  currency entitlements.

Each mutating call expects a JSON-serialisable ``dict`` payload and returns the parsed
response body (also a ``dict``). Long-running operations return a
:class:`~pacx.clients.licensing.LicensingOperation` that records the ``Operation-Location``
header and any metadata returned by the service. Pass the location to
:meth:`LicensingClient.wait_for_operation` to poll until completion.

## CLI commands

The ``licensing`` command group exposes the most common administrative tasks:

- ``ppx licensing billing`` – list policies, fetch details, create/update/delete, manage
  environment assignments, and refresh provisioning (with optional ``--wait`` polling).
- ``ppx licensing allocations currency`` – retrieve or patch currency allocations, plus a
  ``reports`` command for available currency reports.
- ``ppx licensing allocations capacity`` – inspect or patch environment capacity
  allocations.
- ``ppx licensing storage`` – list warning categories and fetch detailed records.
- ``ppx licensing capacity`` – retrieve tenant capacity snapshots or temporary currency
  entitlement counts.

All commands honour ``--api-version`` overrides when the preview API changes, while
defaulting to ``2022-03-01-preview`` to match the published specification.
