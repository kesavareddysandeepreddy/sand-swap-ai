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
- Streamlit (initial)
- React (future)

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
