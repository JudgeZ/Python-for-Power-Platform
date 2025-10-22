
# ADR 0002 — CSV Upsert via OData $batch

**Status**: Accepted
**Context**: Need scalable upserts with per-row outcomes.
**Decision**: Use OData `$batch` changesets; parse response parts to report per-op results; support alternate-key PATCH.

**Consequences**: Multipart parsing implemented, tradeoffs around large batches mitigated via chunking.
