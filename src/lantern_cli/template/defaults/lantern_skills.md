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

Results are written to `.lantern/` (or custom output directory):

- `.lantern/output/{lang}/top_down/` — High-level docs: OVERVIEW, ARCHITECTURE, CONCEPTS, GETTING_STARTED
- `.lantern/output/{lang}/bottom_up/` — Per-file analysis mirroring repository structure
- `.lantern/sense/` — Per-file `.sense` records from batch execution
- `.lantern/lantern_plan.md` — The generated analysis plan

## Reading Results

Start with the top-down documents for a high-level understanding, then dive into bottom-up per-file analyses for detailed insights.
<!-- /lantern-skills -->
