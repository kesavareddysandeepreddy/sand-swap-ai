# Changelog

## Unreleased

- Added intelligent memory-core behaviors for category normalization, duplicate suppression, conflict updates, importance thresholding, and relevance ranking in backend memory services.
- Updated context retrieval to use ranked long-term memory selection so prompts receive the most relevant memories first.
- Added regression tests for duplicate handling, conflict resolution, importance threshold filtering, relevance ranking, restart persistence, and prompt memory-order injection.
- Added memory management API endpoints for listing, filtering, searching, editing, deleting, and bulk deletion of memory records.
- Added React Memory Management UI with filtering, inline edits, detail drawer, and delete operations.
- Added backend API tests for memory CRUD, filtering, ordering, pagination, and bulk deletion behavior.
