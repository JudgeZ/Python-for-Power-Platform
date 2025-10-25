# Changelog

## Unreleased

- Fix polling utilities to raise `TimeoutError` and surface failures in `ppx solution import --wait`.
- Add pagination support to Power Pages downloads to follow `@odata.nextLink` pointers.
- Harden solution archive extraction against Zip Slip directory traversal.
- Ensure Azure Blob binary downloads append SAS tokens even when URLs contain query strings.
- Expose lifecycle management on HTTP-based clients to close connections when finished.
- Strip OData metadata from Power Pages merge uploads to avoid sending non-column keys back to Dataverse.

- 0.2.0 Extended features
