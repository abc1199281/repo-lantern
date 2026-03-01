<!-- lantern-skills -->
# Lantern CLI Skills

Lantern (`repo-lantern`) is an AI-guided codebase analysis tool that generates step-by-step learning narratives for repositories.

## Commands

### Initialize a repository

```bash
lantern init --repo /path/to/repo
```

Options:
- `--repo` — Target repository path (default: `.`)
- `--output` — Custom output directory (default: `.lantern`)
- `--overwrite` / `-f` — Force re-initialization

### Generate an analysis plan

```bash
lantern plan --repo /path/to/repo
```

Options:
- `--planning-mode` — `static` (topological) or `agentic` (LLM-enhanced, default)

### Run full analysis

```bash
lantern run --repo /path/to/repo --lang en
```

Options:
- `--lang` — Output language (`en`, `zh-TW`, etc.)
- `--planning-mode` — `static` or `agentic` (default)
- `--synthesis-mode` — `batch` (rule-based) or `agentic` (LLM-powered, default)
- `--workflow` — Use LangGraph workflow orchestration (default: on)
- `--resume <thread-id>` — Resume from a previous checkpoint
- `--yes` / `-y` — Skip confirmation prompt

## Typical Workflow

1. `lantern init --repo .` — Initialize Lantern config in the repo
2. `lantern plan --repo .` — Generate the analysis plan
3. `lantern run --repo . --lang en` — Execute analysis and generate documentation

## Output Structure

Results are written to `.lantern/` (or custom output directory) as a flat numbered manual:

- `.lantern/output/{lang}/GUIDE.md` — Reading guide and table of contents
- `.lantern/output/{lang}/01-overview.md` — Project overview
- `.lantern/output/{lang}/02-architecture.md` — System architecture
- `.lantern/output/{lang}/03-concepts.md` — Core concepts
- `.lantern/output/{lang}/04-*.md` through `NN-*.md` — Per-file analysis in dependency order
- `.lantern/output/{lang}/NN-getting-started.md` — Getting started guide (last)
- `.lantern/sense/` — Per-file `.sense` records from batch execution
- `.lantern/lantern_plan.md` — The generated analysis plan

Backward-compatible symlinks are provided at `top_down/` and `bottom_up/`.

## Reading Results

Open `GUIDE.md` and read the numbered files in order. The manual starts with high-level overviews, walks through the codebase from foundational modules to entry points, and ends with a getting-started guide.
<!-- /lantern-skills -->
