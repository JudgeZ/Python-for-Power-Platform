
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

## Table sets

- `core`: websites, webpages, webfiles, contentsnippets, pagetemplates, sitemarkers
- `extra`: weblinksets, weblinks, webpageaccesscontrolrules, webroles, entitypermissions, redirects
