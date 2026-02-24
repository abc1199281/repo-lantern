# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-01-01

### Added
- Three-phase analysis pipeline: static analysis, planning, execution, and synthesis
- Multiple LLM backend support: OpenAI, Ollama, OpenRouter, CLI tools
- Psychology-driven batch design using Miller's Law (~3 files per batch)
- Agentic planning mode (`--planning-mode agentic`) for LLM-enhanced plans
- LangGraph workflow mode (`--workflow`) with checkpointing and resume support
- Static dependency graph for Python imports and C++ includes
- Per-file `.sense` records and top-down documentation generation
- Multi-language output support (`--lang`)
- Configuration via `.lantern/lantern.toml` with priority system
- CI pipeline with tests, linting (ruff, black), and type checking (mypy)

[Unreleased]: https://github.com/abc1199281/lantern-cli/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/abc1199281/lantern-cli/releases/tag/v0.1.1
