# Custom Connectors

The `ppx connector` commands manage custom connectors (APIs) hosted in a Power Platform
environment. Every operation requires an access token – either via `PACX_ACCESS_TOKEN`
(set by `ppx auth use` or manual export) or an active profile that supplies an
environment ID.

## List available connectors

```bash
$ ppx connector list --environment-id Default-ENV --top 5
shared-api
custom-connector
```

* Mirrors the behaviour covered by `tests/test_cli_connectors.py::test_connectors_list_formats_output`.
* `$top` is optional; omit it to page with the server default.
* Output renders the connector `name` first, falling back to `id` for legacy
  connectors.

## Push a connector from OpenAPI

```bash
$ ppx connector push \
    --environment-id Default-ENV \
    --name pac-lite \
    --openapi openapi/pac-lite-openapi.yaml
{'name': 'pac-lite', 'status': 'updated'}
```

* The OpenAPI document can be JSON or YAML; the built-in tests feed a YAML payload via
  `tests/test_connectors_client.py::test_put_api_from_openapi`.
* PACX uploads the document to Power Platform and echoes the service response so you
  can confirm the server-side name or provisioning status.

## Update connector metadata

Running `ppx connector push` again against the same connector overwrites the
OpenAPI definition and optional display metadata.

```bash
$ ppx connector push \
    --environment-id Default-ENV \
    --name pac-lite \
    --openapi openapi/pac-lite-openapi.yaml \
    --display-name "PAC Lite"
{'name': 'pac-lite', 'status': 'updated'}
```

* The command issues the same PUT request used in the OpenAPI push path, so
  updates and creates share identical output (see `tests/test_connectors_client.py`).
* Use `--display-name` to change the friendly name shown in Power Apps and
  Power Automate. If you omit the flag, `ppx connector push` sends the
  connector's internal name as `displayName`, replacing any existing friendly
  name; re-supply the current value when you need to keep it.

## Delete a connector

```bash
$ ppx connector delete --environment-id Default-ENV pac-lite
Delete connector 'pac-lite' from environment 'Default-ENV'? [y/N]: y
[green]Deleted connector 'pac-lite' from environment 'Default-ENV'.[/green]

$ ppx connector delete --environment-id Default-ENV --yes pac-lite
[green]Deleted connector 'pac-lite' from environment 'Default-ENV'.[/green]
```

* PACX asks for confirmation before sending the DELETE call. Pass `--yes` (or
  `-y`) to skip the prompt in non-interactive scripts. The behaviour is exercised
  by `tests/test_cli_connectors.py::test_connectors_delete_succeeds`.
* Successful deletions exit with status code `0`. When the connector does not
  exist, PACX prints a friendly not-found message and exits with status `1`
  (`tests/test_cli_connectors.py::test_connectors_delete_handles_404`).
* The client sends the DELETE request with the same API version used across the
  other operations (`tests/test_connectors_client.py::test_delete_api_success`).
