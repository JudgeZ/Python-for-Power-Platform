# Examples

Quick, offline‑friendly examples. These do not require network access.

- Quickstart script: [../examples/quickstart.py](../examples/quickstart.py)
- Quickstart notebook: [../examples/quickstart.ipynb](../examples/quickstart.ipynb)

Try locally

```bash
ppx --version
ppx profile list
```

For authentication flows and CI guidance, see:
- Authentication: [./02-authentication.md](./02-authentication.md)
- CI Examples: [./04-ci-examples.md](./04-ci-examples.md)

## Dataverse CRUD / Query

```bash
# Get a record
ppx dv get accounts 00000000-0000-0000-0000-000000000000

# Create from inline JSON
ppx dv create accounts --data '{"name":"Contoso"}'

# Update from file
ppx dv update accounts 42 --data @payload.json

# Delete
ppx dv delete accounts 42

# Query with OData
ppx dv query accounts --select name,accountnumber --filter "statecode eq 0" --top 10
```

## Solution Flags & Intelligence

```bash
# Export including dependencies
ppx solution export --name MySolution --include-dependencies

# Import with activation/publish/overwrite
ppx solution import --file MySolution.zip --activate-plugins --publish-workflows --overwrite-unmanaged

# Dependencies (DOT)
ppx solution deps --name MySolution --format dot | dot -Tpng -o deps.png

# Components (JSON)
ppx solution components --name MySolution --type 61

# Health check (non-zero exit on missing)
ppx solution check --name MySolution
```

## Environment Wait/Status

```bash
# Copy and wait up to 15 minutes
ppx environment copy env-1 --payload '{"targetEnvironmentName":"copy-env","targetEnvironmentRegion":"unitedstates"}' --wait --timeout 900

# Backup and wait
ppx environment backup env-1 --payload '{"label":"Nightly"}' --wait --timeout 600
```

## Connection References

```bash
# List references (JSON)
ppx connection list --solution MySolution

# Validate (non-zero exit on missing ids)
ppx connection validate --solution MySolution
```
