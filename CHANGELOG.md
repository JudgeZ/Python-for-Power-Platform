# Changelog

## Unreleased

- Fix polling utilities to raise `TimeoutError` and surface failures in `ppx solution import --wait`.
- Add pagination support to Power Pages downloads to follow `@odata.nextLink` pointers.
- Harden solution archive extraction, including SolutionPackager layouts, against Zip Slip directory traversal.
- Ensure Azure Blob binary downloads append SAS tokens even when URLs contain query strings.
- Expose lifecycle management on HTTP-based clients to close connections when finished.
- Include `respx` in the default dependency set so local pytest runs have the required mock tooling.
- Allow Dataverse hosts passed to `DataverseClient` and CLI commands to include the scheme or bare hostname interchangeably.

- 0.2.0 Extended features
