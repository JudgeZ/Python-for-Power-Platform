
# ADR 0004 — Upload Merge Strategies

**Status**: Accepted
**Context**: Different teams prefer distinct sync semantics.
**Decision**: Support `replace|merge|skip-existing|create-only` strategies for upload.
**Consequences**: Extra requests for `merge` (GET before PATCH). Defaults to `replace` for predictability.
