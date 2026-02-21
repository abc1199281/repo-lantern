# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lantern CLI (`repo-lantern` on PyPI) is an AI-guided codebase analysis tool that generates step-by-step learning narratives for repositories. It uses psychology-driven design (Miller's Law chunking, ~3 files per batch) and supports multiple LLM backends (OpenAI, Ollama, OpenRouter, CLI tools).

## Common Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest tests/ -v --cov=lantern_cli --cov-report=term-missing

# Run a single test file
pytest tests/unit/test_architect.py -v

# Run a single test function
pytest tests/unit/test_architect.py::test_function_name -v

# Lint
ruff check src/ tests/
black --check src/ tests/

# Auto-fix lint issues
ruff check src/ tests/ --fix
black src/ tests/

# Type check
mypy src/lantern_cli --ignore-missing-imports

# CLI usage
lantern init --repo /path/to/repo
lantern plan --repo /path/to/repo
lantern run --repo /path/to/repo --lang en
lantern run --workflow --resume <thread-id>
```

## Architecture

The system follows a three-phase pipeline: **Static Analysis → Planning → Execution → Synthesis**.

- **`cli/main.py`** — Typer CLI entry point. Commands: `init`, `plan`, `run`, `version`.
- **`core/architect.py`** — Generates `Plan` with layers and batches from the dependency graph.
- **`core/runner.py`** — Batch execution orchestrator using `StructuredAnalyzer`.
- **`core/synthesizer.py`** — Top-down documentation generator from `.sense` files.
- **`core/workflow.py`** — LangGraph `StateGraph` orchestration with checkpointing/resume.
- **`core/agentic_planner.py`** / **`core/agentic_synthesizer.py`** — LLM-enhanced agentic modes.
- **`llm/backend.py`** — `Backend` Protocol defining the abstract LLM interface.
- **`llm/factory.py`** — Factory that creates backend instances from config.
- **`llm/structured.py`** — Structured output handling for batch analysis.
- **`static_analysis/dependency_graph.py`** — Builds dependency graph from Python imports and C++ includes.
- **`config/loader.py`** — `ConfigLoader` with priority system; reads `.lantern/lantern.toml`.
- **`template/`** — Prompt templates organized by phase (bottom_up, synthesis, planning, agent, memory).

**Three operating modes:** static planning, agentic planning (`--planning-mode agentic`), and full LangGraph workflow (`--workflow`).

## Backend / Vendor Boundary (from AGENTS.md)

- Provider-specific code (SDK construction, auth, transport) lives only in `llm/backends/`.
- Business/orchestration logic belongs in `core/` and `llm/`.
- Do not mix provider concerns with domain logic.

## Code Style

- **Black**: line-length 100, target Python 3.10
- **Ruff**: rules E, F, I, N, W, UP; line-length 100
- **MyPy**: strict (`disallow_untyped_defs = true`)
- Google-style docstrings
- Pre-commit hooks enforce all of the above (`pre-commit install`)

## Output Structure

Analysis results go into `.lantern/`:
- `.lantern/sense/` — Per-file `.sense` records from batch execution
- `.lantern/output/{lang}/top_down/` — OVERVIEW, ARCHITECTURE, CONCEPTS, GETTING_STARTED
- `.lantern/output/{lang}/bottom_up/` — Per-file analysis mirroring repo structure

## Testing

Tests live in `tests/unit/` and `tests/integration/`. Fixtures are in `tests/conftest.py` and `tests/fixtures.py`. CI runs tests on Python 3.10, 3.11, 3.12.
