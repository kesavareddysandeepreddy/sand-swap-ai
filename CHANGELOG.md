# Changelog

## Unreleased

- Added Sprint 7 production-ready MCP framework under `backend/mcp` with client/server abstractions, metadata registry, capability discovery snapshots, transport abstraction (stdio/http/sse/websocket-ready), session/heartbeat state tracking, ToolRouter MCP invocation integration, planner/workflow/runtime MCP tool support, DI registrations, and MCP regression tests without API/UI changes.
- Added Sprint 6 generic Workflow Engine under `backend/workflows` with workflow/task/context/result models, execution-plan-to-workflow conversion, sequential executor with retries/failure rollback/cancellation, in-memory workflow queue, workflow type registry, structured lifecycle logging, Agent Runtime workflow execution integration, ToolRouter task invocation support, DI registrations, and regression coverage.
- Added Sprint 5 generic Agent Runtime under `backend/agents` with base agent interfaces, planner, registry, tool router, execution engine, runtime orchestration, default GeneralChatAgent, extension-point agent interfaces, DI registrations, and chat execution routed through AgentRuntime without API changes.
- Added Sprint 4 Knowledge Object Engine under `backend/knowledge` with strongly typed knowledge models, repository abstraction + in-memory implementation, registry/index/context builders, lifecycle service integration on upload, multimodal pipeline migration to knowledge-object outputs, conversation knowledge-id mapping, cache/version handling, DI registrations, and comprehensive knowledge regression tests.
- Added Sprint 3 multimodal chat integration with a staged multimodal pipeline (attachment, vision, context), automatic image understanding injection into chat prompts, conversation-level attachment/analysis processing state, cache-aware reuse, graceful fallback behavior, and regression-safe test coverage including upload-to-chat integration.
- Added Sprint 2 multimodal image understanding with an Ollama vision provider, startup vision-model discovery, cached image analysis, structured attachment context generation, provider health/capability reporting, graceful no-model fallback, and expanded multimodal tests.
- Added Sprint 1 multimodal infrastructure under `backend/multimodal` including typed attachment models, attachment routing/type classification, provider interfaces and registry, placeholder attachment context builder, in-memory image cache, config scaffolding, DI registration, and unit tests without changing existing APIs.
- Added enterprise project management with nested project scopes under workspaces, including project CRUD/switch APIs, active project persistence, and ownership context expansion to user-workspace-project isolation.
- Extended chat, memory, and document retrieval/upload flows to enforce workspace and project scoping via request context headers and service-level filters.
- Added frontend workspace/project selector state and API integration for project create/rename/delete/switch behavior.
- Added regression coverage for project APIs and updated scope-aware backend/frontend tests to validate workspace-project isolation behavior.
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
- Expanded universal parser coverage for enterprise formats including HTML, ZIP archives (recursive), logs, config variants, batch scripts, and additional image extensions.
- Added pluggable OCR provider abstraction for image parsing with configurable provider selection.
- Enriched ingestion metadata with parser name, source type, pages/tables/images counts, section/paragraph counts, checksum/file-size diagnostics, and processing time/status.
- Enhanced Retrieval Inspector and Documents UI to surface parser diagnostics, score breakdowns, match reasons, highlighted query terms, and source metadata drilldown.
