# User Management

Power Platform exposes limited user-management APIs for assigning and removing admin roles.
PACX surfaces these capabilities through a lightweight client and CLI commands that wrap
the preview `usermanagement` endpoints.

## Required permissions

* **OAuth scope**: request tokens with the `https://api.powerplatform.com/.default`
  scope when using client credentials or device code flows.
* **Directory roles**: the calling principal must hold either the
  `Privileged Role Administrator` or `Global Administrator` Azure AD/Entra role to
  apply or remove tenant-level admin assignments. These elevated roles are required
  because the API mutates administrator privileges.

Without both the correct scope and directory role, the service will return `403`
responses even when the request payload is well-formed.

## CLI usage

PACX registers the `users admin-role` command group when the CLI module is imported.
All commands accept Azure AD object IDs for the target user and default to the
`2022-03-01-preview` API version.

### Apply the admin role

```bash
ppx users admin-role apply 00000000-0000-0000-0000-000000000000
```

The command waits for completion by default and prints the async operation status. Use
`--no-wait` to return immediately after the service accepts the request. Customize the
polling cadence via `--interval` (seconds) and `--timeout` (seconds).

### Remove an admin role assignment

```bash
ppx users admin-role remove 00000000-0000-0000-0000-000000000000 \
  --role-definition-id 11111111-1111-1111-1111-111111111111
```

The `--role-definition-id` option is required and should match the identifier returned by
`users admin-role list` when viewing existing assignments. As with the apply command, the
CLI polls for completion unless `--no-wait` is supplied.

### List assigned admin roles

```bash
ppx users admin-role list 00000000-0000-0000-0000-000000000000
```

Lists all current admin assignments for the specified user, including the role definition
ID, display name, and scope.
