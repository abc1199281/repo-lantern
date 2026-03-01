# Lantern Roadmap

> **Last Updated**: 2026-02

Future development plans for Lantern, organized by priority.

---

## P0 — Near-term

### ~~Incremental Update~~ ✅
Support partial re-analysis after code changes. Detect modified files via `git diff` or file hashes, re-analyze affected batches and their dependents, then regenerate top-down docs.

### ~~Spec-Aware Documentation~~ ✅
Associate specification documents (PDF/Markdown) with code modules via `lantern spec add`. LLM auto-maps specs to source modules, and spec context is injected into bottom-up analysis, agentic planning, and synthesis prompts. Mappings stored in `.lantern/specs.toml`.

### Static Analysis Expansion (Go + Rust)
Add dependency graph support for Go (`import` statements) and Rust (`use` / `mod` statements) alongside existing Python and C++ analyzers.

---

## P1 — Mid-term

### VSCode Extension
IDE integration for progress tracking, Mermaid preview, hover summaries, and one-click analysis.

### Direct API Support (Gemini / Claude SDK)
Native SDK backends for Google Gemini and Anthropic Claude, bypassing OpenRouter for lower latency and cost.

### Execution Trace Mode
Collect runtime call graphs from unit tests to enrich analysis with dynamic information (hot paths, call frequency).

---

## P2 — Long-term

### Community Templates
Share and discover community-contributed prompt templates (`lantern templates list/publish`).

### Live Codebase Monitoring
Watch for file changes and automatically trigger incremental re-analysis in the background.

### AI Tutor Mode
Interactive learning assistant that guides developers through a codebase using generated docs and RAG.

### Multi-modal Support
Analyze architecture diagrams and screenshots alongside source code using vision LLMs.

---

## Success Metrics

- **Doc quality**: user rating 4.5+/5.0
- **Cost efficiency**: average < $3 per repository
- **Test coverage**: 90%+
- **Execution time**: < 5 min for 100-file repo

---

## Community Contribution Priorities

- New language analyzers (Java, JavaScript, TypeScript)
- Community prompt templates
- VSCode Extension development
- Performance optimizations (parallelism, caching)
