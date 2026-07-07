# SandSwap AI Development Instructions

You are contributing to SandSwap AI.

## Mission

SandSwap AI is a production-grade, local-first AI Operating System.

Every change must move the project toward production quality.

---

# Architecture

Follow Clean Architecture.

backend/
    core/
    domain/
    memory/
    llm/
    retrieval/
    vectordb/
    agents/
    workflows/
    api/

Never violate module boundaries.

---

# Coding Standards

- Python 3.12+
- Full type hints
- Google-style docstrings
- SOLID principles
- DRY
- Composition over inheritance
- Small focused classes
- Dependency injection where appropriate

Never use placeholder implementations.

---

# Existing Components

Reuse existing modules whenever possible.

Current implementations include:

- MemoryManager
- SQLiteMemoryStore
- MemoryRecord
- OllamaClient
- PromptManager
- LLMMemoryExtractor
- Service Container
- Lifecycle Manager

Do not duplicate functionality.

---

# Code Quality

Every implementation must:

- Pass Ruff
- Pass Black
- Pass MyPy
- Pass Pytest

Avoid breaking existing public APIs.

---

# Documentation

Whenever implementing a feature:

Update:

- CHANGELOG.md
- README.md (if applicable)
- docs/

---

# Testing

Every feature must include:

- Unit tests
- Edge cases
- Error handling

Never leave untested production code.

---

# Performance

Prefer:

- async where appropriate
- lazy loading
- dependency injection
- reusable services

Avoid unnecessary allocations.

---

# AI Guidelines

Before creating a new class:

1. Search the repository.
2. Reuse existing implementations.
3. Extend existing services instead of duplicating them.

Never create duplicate managers.

---

# Output Expectations

Generate production-quality code.

Avoid placeholders.

Avoid TODO comments.

Avoid mock implementations unless explicitly requested.

Always leave the repository in a buildable state.