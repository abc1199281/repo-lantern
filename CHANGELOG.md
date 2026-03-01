# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `lantern spec add` command to associate specification documents (PDF/Markdown) with code modules
- `lantern spec list` and `lantern spec remove` commands for managing spec mappings
- LLM auto-mapping: automatically determines which modules a spec covers
- Spec context injection into bottom-up analysis, agentic planning, and synthesis prompts
- PDF text and table extraction via pdfplumber
- `.lantern/specs.toml` as single source of truth for spec-to-module mappings

## [0.1.3] - 2026-02-24

### Added
- `lantern update` command for git diff-based incremental analysis — only re-analyzes changed files and their direct dependents
- `lantern onboard` command to generate AI coding tool instructions (Codex, Copilot, Claude)
- `DiffTracker` module for git change detection and impact set calculation
- File manifest tracking in `state.json` for incremental updates
- Git commit SHA recorded after analysis for diff baseline
- Stale artifact cleanup for deleted/renamed files

### Fixed
- Resolve `--output` path relative to CWD instead of repo path
- Pass `output_dir` to `StateManager` so `state.json` respects `--output`
- Filter unknown fields when loading `ExecutionState` from `state.json` (forward-compat)
- Remove invalid `model_name` / `is_local` kwargs in `update` command Runner call
- Handle missing end marker in `_write_skills` to prevent `ValueError` on corrupted sections

## [0.1.2] - 2026-02-24

### Added
- Mermaid syntax validation with LLM auto-repair for generated diagrams
- Meaningful progress bar with batch phases and elapsed time
- `--planning-mode` and `--lang` options for `plan` command
- TypeScript/JavaScript language support for static analysis
- LangSmith observability integration
- GitHub Actions release workflow with PyPI trusted publishing
- CHANGELOG.md following Keep a Changelog format

### Changed
- Unified version management via `importlib.metadata` (single source in `pyproject.toml`)

### Fixed
- Always override LLM language with requested configuration language
- Skip empty files to prevent LLM hallucination in bottom-up analysis
- Replace language-specific sentinel with empty summary for empty file stubs
- Python 3.10 compatibility for `tomllib` import
- Agentic flow fixes

### Removed
- English-first translation approach (reverted for consistent language output)

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

[Unreleased]: https://github.com/abc1199281/repo-lantern/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/abc1199281/repo-lantern/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/abc1199281/repo-lantern/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/abc1199281/repo-lantern/releases/tag/v0.1.1
