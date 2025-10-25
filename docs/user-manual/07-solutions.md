# Solutions

`ppx solution` orchestrates solution lifecycle tasks against Dataverse and the
Power Platform API. Commands that talk to Dataverse require:

* An access token exposed via `PACX_ACCESS_TOKEN` or a configured profile (`ppx auth use`).
* A Dataverse host supplied with `--host` or through the `DATAVERSE_HOST` environment variable.

> **Note:** `ppx solution --action <command>` and positional invocations are
> still supported for backward compatibility, but the CLI prints a single deprecation
> warning per process. Prefer the explicit subcommand form (`ppx solution <command>`) in
> scripts so the shim can be removed in a future release.

## List installed solutions

```bash
$ ppx solution list --host example.crm.dynamics.com
core_solution  Core Solution  v1.2.3.4
```

* Matches the behaviour asserted in `tests/test_cli_solutions.py::test_solution_list_formats_output`.
* The table shows the unique name, display name, and version for every solution in the
  target environment.

## Export managed or unmanaged packages

```bash
$ ppx solution export \
    --host example.crm.dynamics.com \
    --name contoso_solution \
    --managed \
    --out dist/contoso_solution_managed.zip
Exported to dist/contoso_solution_managed.zip
```

* Omit `--managed` to export an unmanaged package; use `--out` (or `--file`) to control the file name.
* The command wraps `DataverseClient.export_solution` with the managed flag that is already
  covered by the OpenAPI model in `pacx.models.dataverse`.
* Exported zips can be fed directly into an import or unpacked with the commands below.

## Import a solution and wait for completion

```bash
$ ppx solution import \
    --host example.crm.dynamics.com \
    --file dist/contoso_solution_managed.zip \
    --import-job-id job123 \
    --wait
Import submitted (job: job123)
{'status': 'Completed'}
```

* Mirrors the CLI flow tested by `tests/test_cli_solutions.py::test_solution_import_waits_and_reports`.
* Provide `--wait` to poll `ImportJobId` (defaults to a generated GUID when omitted) until the job
  reaches a terminal state.
* For fire-and-forget automation, drop `--wait` and capture the echoed job ID for later monitoring.
* Long-running imports poll every second for up to 10 minutes; if the timeout is reached the command exits with the last known
  status so you can decide whether to retry or continue monitoring in the Power Platform admin center.
* After a successful import, run `ppx solution list` to confirm the version bump and `ppx solution publish-all` if the package
  introduced unmanaged customizations that require publication.

## Publish all customizations

```bash
$ ppx solution publish-all --host example.crm.dynamics.com
Published all customizations
```

* Requires the same Dataverse prerequisites as import/export.
* Useful after applying unmanaged customizations that touch multiple solutions. Publish operations can take several minutes in
  large environments; keep the terminal open until the Rich status message returns.

## Pack and unpack solution archives

### Direct zip pack/unpack

```bash
$ ppx solution unpack --file dist/contoso_solution_managed.zip --out solution_unpacked
Unpacked dist/contoso_solution_managed.zip -> solution_unpacked

$ ppx solution pack --src solution_unpacked --out dist/contoso_solution_managed.zip
Packed solution_unpacked -> dist/contoso_solution_managed.zip
```

* These commands keep the original archive structure intact – ideal for quick edits or inspecting manifests.
* The helper functions (`pacx.solution_source.pack_solution_folder` and `.unpack_solution_zip`) preserve every file under
  the root without reformatting component folders.
* When using temporary working folders (e.g., `solution_unpacked`), remember to clean them up (`rm -rf solution_unpacked`) or
  add them to `.gitignore` so build artifacts do not bleed into commits.

### SolutionPackager-like layout

```bash
$ ppx solution unpack-sp --file dist/contoso_solution_managed.zip --out solution_src
Unpacked (SolutionPackager-like) dist/contoso_solution_managed.zip -> solution_src

$ tree solution_src
solution_src/
└── src/
    ├── CanvasApps/
    ├── PluginAssemblies/
    ├── WebResources/
    ├── Workflows/
    └── Other/

$ ppx solution pack-sp --src solution_src/src --out dist/contoso_solution_managed.zip
Packed (SolutionPackager-like) solution_src/src -> dist/contoso_solution_managed.zip
```

* The folder names come from `pacx.solution_sp.COMPONENT_MAP`; root-level files such as `solution.xml`
  land under `Other/` to round-trip cleanly.
* `unpack-sp` always creates a `src/` directory so you can track exports in source control, and `pack-sp`
  reverses the projection before zipping.
* The `src/` projection mirrors SolutionPackager conventions, making it easy to diff between environments with Git. Clean up
  the staging tree after packaging to avoid stale files (`rm -rf solution_src`).
* `unpack_to_source` rejects entries that would escape the destination tree, preventing Zip Slip-style traversal attacks when processing untrusted archives.
