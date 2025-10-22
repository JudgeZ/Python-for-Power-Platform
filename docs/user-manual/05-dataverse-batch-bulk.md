
# Dataverse $batch & Bulk CSV

```bash
ppx dv bulk-csv accounts data.csv --id-column accountid --chunk-size 50 --report result.csv
```
The report includes per-operation status and JSON payload (if any).
