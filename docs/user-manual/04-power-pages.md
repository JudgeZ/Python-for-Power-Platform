
# Power Pages

## Download

```bash
ppx pages download --website-id <GUID> --tables full --out site_dump --host <DV> \
  --binary-provider annotations --binary-provider azure \
  --provider-options provider_opts.json
```

* `--binary-provider` may be specified multiple times. Built-ins: `annotations` (Dataverse notes) and `azure` (virtual file storage).
* Provider options can be passed inline JSON or as a file mapping provider name to settings (`top`, `sas_env`, etc.).
* `manifest.json` captures table summaries, provider results (checksums), and the natural key configuration used for uploads.
* `annotations` honors an optional `top` limit (default: 50 notes per web file) and records missing `documentbody` are surfaced in the manifest as skipped entries so you can backfill the note content.
* `azure` (alias for `azure-blob`) appends files under `files_virtual/` and expects a Shared Access Signature to be available when blobs are private. Export the token to an environment variable and reference it through provider options: `--provider-options '{"azure": {"sas_env": "PACX_BLOB_SAS"}}'`.
* Binary providers sanitize filenames before writing to disk. Path separators are stripped, `..` segments collapse to the basename, and any path that would resolve outside the export directory is rejected. The manifest records the sanitized relative path alongside the checksum so you can compare exports safely.

Set `--include-files false` to skip `adx_webfiles`; binary providers require files to be included.

## Upload

```bash
ppx pages upload --website-id <GUID> --src site_dump --host <DV> \
  --strategy merge --key-config keys.json
```

* Strategies: `replace` (default), `merge`, `skip-existing`, `create-only`.
  * `replace`: full refresh that overwrites Dataverse with `site_dump`. Useful when publishing from a known-good branch: `ppx pages upload --strategy replace --src site_dump`.
  * `merge`: apply incremental edits without disturbing untouched records. Ideal for tweaking copy or templates: `ppx pages upload --strategy merge --src site_dump`.
  * `skip-existing`: seed new entities while leaving anything already provisioned in Dataverse intact, e.g. populating a new sandbox: `ppx pages upload --strategy skip-existing --src site_dump`.
  * `create-only`: fail instead of updating existing rows, letting you validate that the target really is empty before the first deployment.
* Natural keys default to the manifest values, but `--key-config` (inline JSON or file) can override per entity.
* After an upload, rerun `ppx pages download` and compare `manifest.json` with the pre-upload version (`git diff site_dump/manifest.json`) to verify that checksums and key metadata match expectations.

## Diff permissions

```bash
ppx pages diff-permissions --website-id <GUID> --src site_dump --host <DV>
```

Generates a plan grouped by entity (`adx_entitypermissions`, `adx_webpageaccesscontrolrules`, `adx_webroles`) identifying `create`, `update`, and `delete` operations needed to align Dataverse with the local export.

### Provider options & key overrides

Binary provider configuration is normalized by the Power Pages client before downloads. The CLI accepts a JSON string or file for `--provider-options`; the client canonicalizes provider names, validates that each option is a JSON object, and feeds those values to the providers that execute. When custom providers are requested, `--include-files` must stay enabled because providers operate over the exported `adx_webfiles`.

`azure-blob` requests may fail when a blob is private and no SAS token is supplied; the CLI records these HTTP errors inside `manifest.json -> providers[].errors` so you can rerun the download after fixing credentials. You can also raise the client timeout via `PACX_BLOB_TIMEOUT` (seconds) when large virtual files are slow to stream.

For uploads and permission diffs, the client composes the natural key map by layering three sources:

1. Built-in defaults for each entity.
2. Natural keys stored in the export's `manifest.json`.
3. Optional overrides supplied via `--key-config`.

This means a new override only needs to mention the entity it modifies; the rest of the manifest defaults continue to apply.

## Table sets

- `core`: websites, webpages, webfiles, contentsnippets, pagetemplates, sitemarkers
- `full`: `core` plus weblinksets, weblinks, webpageaccesscontrolrules, webroles, entitypermissions, redirects

Individual folders or entitysets can be requested by name. Comma-separated values are additive, so
`--tables core,weblinks` exports the `core` set plus `weblinks`. The Typer CLI also accepts
multiple `--tables` options (e.g., `--tables pages --tables weblinks`) to achieve the same result.

### Verifying downloads

After exporting, inspect the `manifest.json` to review the binary provider outcomes and natural key map. To spot drift between environments, diff manifests from two exports:

```bash
ppx pages download --website-id <GUID> --out prod_dump --host <PROD>
diff -u site_dump/manifest.json prod_dump/manifest.json
```

Provider `files` entries surface checksum differences, while mismatched `natural_keys` entries indicate configuration drift that should be reconciled before the next upload.
