
# ADR 0003 — Power Pages Sync

**Status**: Accepted
**Context**: Teams want site artifacts in source control with optional binaries.
**Decision**: Emit one JSON per record per table group, plus optional `files_bin/` extracts via Notes (`annotations`) with checksums.
**Consequences**: Simplicity over completeness; can extend to more tables and richer diff/merge later.
