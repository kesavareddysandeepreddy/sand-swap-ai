# SandSwap AI

> Your Personal AI Operating System

## Vision

SandSwap AI is a production-grade, fully local AI platform designed around:

- Persistent Long-Term Memory
- Multi-Agent Intelligence
- Advanced RAG
- Knowledge Graph
- Local LLMs
- Plugin Architecture
- Workflow Automation

## Current Status

- [x] Sprint 01 - Foundation (In Progress)
- [ ] Sprint 02 - Memory Engine
- [ ] Sprint 03 - Local LLM
- [ ] Sprint 04 - RAG Engine
- [ ] Sprint 05 - Multi-Agent Framework

## Project Structure

backend/
frontend/
docs/
docker/
scripts/
data/

## Tech Stack

- Python 3.12+
- FastAPI
- Ollama
- Qdrant
- Docker
- React + Vite + TypeScript

## Roadmap

See:

docs/roadmap/

## Running API

Start the FastAPI runtime locally with:

```bash
uvicorn backend.api.main:app --reload
```

## Running tests

Run the test suite with:

```bash
pytest
```

Frontend validation:

```bash
cd frontend
npm run lint
npm run build
```

## Google OAuth Configuration

Set these environment variables to control OAuth callback and post-login redirect URLs.

Development:

```bash
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8007/auth/oauth/google/callback
FRONTEND_POST_LOGIN_URL=http://127.0.0.1:5173/chat
```

Production:

```bash
GOOGLE_OAUTH_REDIRECT_URI=https://ai.testlabs.co.in/auth/oauth/google/callback
FRONTEND_POST_LOGIN_URL=https://ai.testlabs.co.in/chat
```

If these variables are not set, SandSwap AI preserves localhost fallback behavior.

## Memory API

Memory management endpoints are available under `/memory`:

- `GET /memory` - list memories with `page`, `page_size`, `search`, `category`, and `min_importance` filters
- `GET /memory/{memory_id}` - fetch a single memory
- `PATCH /memory/{memory_id}` - edit category/key/value/importance
- `DELETE /memory/{memory_id}` - delete a single memory
- `DELETE /memory` - delete all memories

See `docs/api/memory-management.md` for details and payload schemas.

## Documents API (Universal Ingestion + RAG)

Universal ingestion and retrieval endpoints are available under `/documents`:

- `POST /documents/upload` - upload, parse, chunk, embed, and index a document
- `GET /documents` - list all uploaded documents
- `GET /documents/{document_id}` - fetch one document metadata record
- `GET /documents/{document_id}/chunks` - inspect indexed chunks for a document
- `POST /documents/retrieve` - run semantic retrieval with filters for debugging
- `DELETE /documents/{document_id}` - delete one document and its index entries
- `DELETE /documents` - delete all documents and indexed chunks

Current parser coverage includes office documents, spreadsheets, presentations, markdown/text/logs,
JSON/XML/YAML/TOML/INI/config, source code and scripts, email files, HTML pages, images (with OCR hooks),
engineering specs, and recursive ZIP archive ingestion.

The ingestion metadata now exposes parser and processing diagnostics via each document's `metadata`
payload (for example: `parser`, `pages`, `tables`, `images`, `processing_time_ms`, and `processing_status`).

See `docs/api/rag-platform.md` for payloads and architecture notes.

## Formatting

Format Python source files with:

```bash
black .
isort .
```

## Linting

Run lint checks with:

```bash
ruff check .
```

## Development workflow

1. Create and activate a virtual environment in `.venv`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the API locally with `uvicorn backend.api.main:app --reload`.
4. Execute `pytest`, `ruff check .`, `black .`, and `isort .` before submitting changes.

## License

Apache-2.0
