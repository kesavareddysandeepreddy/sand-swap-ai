# Changelog

## Unreleased

- Added intelligent memory-core behaviors for category normalization, duplicate suppression, conflict updates, importance thresholding, and relevance ranking in backend memory services.
- Updated context retrieval to use ranked long-term memory selection so prompts receive the most relevant memories first.
- Added regression tests for duplicate handling, conflict resolution, importance threshold filtering, relevance ranking, restart persistence, and prompt memory-order injection.
- Added memory management API endpoints for listing, filtering, searching, editing, deleting, and bulk deletion of memory records.
- Added React Memory Management UI with filtering, inline edits, detail drawer, and delete operations.
- Added backend API tests for memory CRUD, filtering, ordering, pagination, and bulk deletion behavior.
- Added enterprise RAG foundation under backend/rag with parser/chunker/embedding/vector store/retriever interfaces and factories.
- Added universal document ingestion API under `/documents` with upload, list, get, chunk inspection, retrieval inspector, single delete, and bulk delete endpoints.
- Added SQLite-backed document metadata repository and SQLite vector similarity store with metadata-aware filtering.
- Added prompt-context extension to inject retrieved document chunks and citations between long-term memory and conversation history.
- Added React Documents and Retrieval Inspector pages with upload, filter, list, viewer, and retrieval-debug UX.
- Added backend RAG tests for parser/chunker routing, upload/index/retrieve APIs, and vector retrieval behavior.
- Added frontend test scaffolding (Vitest + Testing Library) with page tests for Documents and Retrieval Inspector.
