
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

Set `--include-files false` to skip `adx_webfiles`; binary providers require files to be included.

## Upload

```bash
ppx pages upload --website-id <GUID> --src site_dump --host <DV> \
  --strategy merge --key-config keys.json
```

* Strategies: `replace` (default), `merge`, `skip-existing`, `create-only`.
* Natural keys default to the manifest values, but `--key-config` (inline JSON or file) can override per entity.

## Diff permissions

```bash
ppx pages diff-permissions --website-id <GUID> --src site_dump --host <DV>
```

Generates a plan grouped by entity (`adx_entitypermissions`, `adx_webpageaccesscontrolrules`, `adx_webroles`) identifying `create`, `update`, and `delete` operations needed to align Dataverse with the local export.

### Provider options & key overrides

Binary provider configuration is normalized by the Power Pages client before downloads. The CLI accepts a JSON string or file for `--provider-options`; the client canonicalizes provider names, validates that each option is a JSON object, and feeds those values to the providers that execute. When custom providers are requested, `--include-files` must stay enabled because providers operate over the exported `adx_webfiles`.

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
