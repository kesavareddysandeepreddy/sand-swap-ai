# Universal Knowledge Ingestion and RAG API

This document describes the universal ingestion + retrieval platform introduced in EWP-008.

## Architecture

The backend implementation lives in `backend/rag/` and follows clean boundaries:

- `domain/` - contracts and entities (`DocumentParser`, `Chunker`, `EmbeddingProvider`, `VectorStore`, `Retriever`)
- `parsers/` - parser implementations plus `ParserFactory`
- `chunkers/` - specialized chunkers plus `ChunkerFactory`
- `embeddings/` - provider implementations and factory
- `vectorstores/` - SQLite vector index implementation
- `infrastructure/` - SQLite document metadata repository
- `application/` - ingestion and retrieval services
- `api/` - FastAPI routes and schemas

## Data Flow

1. Upload file to `POST /documents/upload`
2. File is persisted to `data/documents/` with UUID-prefixed storage name
3. `ParserFactory` resolves parser from file-type registry
4. Parsed text is passed to specialized chunker
5. Chunks are embedded via configured embedding provider
6. Chunk vectors are indexed in SQLite vector store
7. Document metadata and status are updated in SQLite repository

## Endpoints

### POST /documents/upload

Multipart form fields:

- `file` (required)
- `project` (optional)
- `tags` (optional comma-separated)
- `chunk_size` (optional)
- `overlap` (optional)

Returns indexed document metadata including `chunk_count`, `embedding_status`, and `index_status`.

### GET /documents

Returns all uploaded documents ordered by newest first.

### GET /documents/{document_id}

Returns metadata for one document.

### GET /documents/{document_id}/chunks

Returns indexed chunks for a document with chunk metadata.

### POST /documents/retrieve

Request body:

```json
{
  "query": "how to deploy service",
  "top_k": 8,
  "document_id": null,
  "file_type": null,
  "category": null
}
```

Response:

- `chunks`: retrieved chunk payloads with similarity score and metadata
- `citations`: source lines formatted as `Document | page | section | chunk`

### DELETE /documents/{document_id}

Deletes one document plus associated indexed chunks.

### DELETE /documents

Deletes all stored documents and all indexed vectors.

## Prompt Injection Order

The chat context builder now injects prompt sections in this order:

1. System prompt
2. Relevant long-term memory
3. Relevant retrieved documents (+ citations)
4. Conversation history
5. Current user question

## Frontend

Two new pages were added:

- `/documents` - upload/list/filter/delete/view metadata/chunks
- `/inspector` - run ad-hoc retrieval queries and inspect scores/citations

These pages are accessible from the sidebar navigation.
