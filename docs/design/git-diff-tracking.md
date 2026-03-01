# Design: Git Diff-based Incremental Tracking

## Problem Statement

Lantern currently performs full analysis on every `lantern run`. After a repository has been
analyzed once, subsequent runs should detect what changed (via `git diff`) and only re-analyze
affected files — saving time and LLM cost.

## Pipeline Overview

```
lantern update --repo /path/to/repo
        │
        ▼
┌─────────────────────────┐
│ 1. Load state.json      │ ← Retrieve last analysis git commit SHA
│    get git_commit_sha   │
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 2. git diff <sha>..HEAD │ ← Get change list
│    --name-status -M     │   A(added) M(modified) D(deleted) R(renamed)
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 3. Rebuild Dep Graph    │ ← Import relationships may have changed
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 4. Calculate Impact Set │ ← Changed files + reverse dependencies
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 5. Clean stale artifacts│ ← Remove .sense / bottom_up for deleted files
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 6. Incremental Re-plan  │ ← Batch only the impact set files
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 7. Execute (Runner)     │ ← Run only new batches
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 8. Update state.json    │ ← Write new git_commit_sha + file_manifest
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│ 9. Re-synthesize        │ ← Regenerate top-down docs from all .sense files
└──────────┘──────────────┘
```

## Key Design Decisions

### 1. State Extension (`state.json`)

Add two new fields to `ExecutionState`:

```json
{
  "last_batch_id": 5,
  "completed_batches": [1, 2, 3, 4, 5],
  "failed_batches": [],
  "global_summary": "...",
  "git_commit_sha": "a1b2c3d4e5f6...",
  "file_manifest": {
    "src/main.py": {
      "batch_id": 1,
      "sense_file": "batch_0001.sense",
      "status": "success"
    },
    "src/config.py": {
      "batch_id": 1,
      "sense_file": "batch_0001.sense",
      "status": "success"
    }
  }
}
```

- **`git_commit_sha`**: HEAD commit at the time of last analysis completion. Used as
  the base for `git diff`.
- **`file_manifest`**: Maps each analyzed file to its batch/sense file for efficient
  incremental updates.

### 2. Impact Propagation Strategy

When `file_A.py` is modified:

```
file_A.py (modified)          ← Direct change — always re-analyze
    ↑
file_B.py (imports file_A)    ← Level 1 dependent — re-analyze
    ↑
file_C.py (imports file_B)    ← Level 2+ — skip (handled by re-synthesis)
```

**Strategy: Direct changes + Level 1 reverse dependencies.**

- **Must re-analyze**: A (Added) and M (Modified) files from git diff
- **Should re-analyze**: Direct reverse dependencies of changed files (their `.sense`
  records likely reference functions/classes that changed)
- **Skip re-analysis**: Level 2+ indirect dependents (re-synthesis from updated
  `.sense` files is sufficient)
- **Clean up**: D (Deleted) files — remove their `.sense` records and bottom-up docs

Rationale: Level 1 dependents directly reference the changed files in their analysis
(via `references`, `flow`, etc.). Deeper dependents are only indirectly affected, and
the Synthesis phase (which reads all `.sense` files) naturally captures these cascading
changes.

### 3. New Module: `core/diff_tracker.py`

```python
@dataclass
class DiffResult:
    added: list[str]                  # New files
    modified: list[str]               # Modified files
    deleted: list[str]                # Deleted files
    renamed: list[tuple[str, str]]    # (old_path, new_path)

@dataclass
class ImpactSet:
    reanalyze: set[str]     # Files that need re-analysis
    remove: set[str]        # Files whose artifacts should be cleaned
    reason: dict[str, str]  # file_path → reason for inclusion (for logging)

class DiffTracker:
    def __init__(self, repo_path: Path) -> None: ...

    def get_current_commit(self) -> str:
        """Get HEAD commit SHA via `git rev-parse HEAD`."""

    def get_diff(self, base_sha: str) -> DiffResult:
        """Run `git diff <base_sha>..HEAD --name-status -M` and parse."""

    def calculate_impact(
        self, diff: DiffResult, dep_graph: DependencyGraph
    ) -> ImpactSet:
        """Combine diff result with dependency graph to compute full impact."""
```

### 4. Rename Handling

`git diff -M` detects renames with similarity scores:

- **Pure rename (100% similar)**: Update `file_manifest` mapping, reuse existing
  `.sense` record (update `file_path` field). No re-analysis needed.
- **Rename + modify (< 100% similar)**: Treat as modified — re-analyze the new path,
  clean up old path artifacts.

### 5. `.sense` File Management

Current format: batch-level files (`batch_0001.sense`) containing arrays of per-file
records.

**Short-term (Phase 1):** If any file in a batch needs re-analysis, re-run the entire
batch. Batch size is 3, so the overhead is minimal.

**Long-term (Phase 2):** Migrate to per-file `.sense` files (e.g., `src__main_py.sense`)
for precise incremental updates without touching unrelated files.

### 6. CLI Command

```bash
# New dedicated command
lantern update --repo /path/to/repo [--lang en]

# Auto-detection in existing run command
lantern run --repo /path/to/repo
# → If state.json has git_commit_sha, prompt:
#   "Previous analysis found. Use `lantern update` for incremental analysis."
```

### 7. Large-Change Threshold

If the impact set exceeds 50% of total analyzed files, incremental analysis offers
little benefit. Recommend full re-analysis:

```python
if len(impact_set.reanalyze) > 0.5 * len(file_manifest):
    console.print("Over 50% of files affected. Consider full re-analysis.")
```

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Not a git repo | Error: require git for `update` command |
| Stored SHA doesn't exist (force push/rebase) | Detect failure, suggest full re-analysis |
| Branch switch (completely different branch) | Warn user, suggest full re-analysis |
| `lantern.toml` filter config changed | File set may differ entirely — suggest full re-analysis |
| Only non-code files changed (.md, .txt) | FileFilter excludes them — no re-analysis triggered |
| >50% files changed | Suggest full re-analysis (threshold warning) |
| Merge commits | `git diff` handles naturally |

## Data Flow Diagram

```
                ┌──────────┐
                │ Git Repo │
                └────┬─────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │git diff │ │Dep Graph│ │FileFilter│
    │(changes)│ │(imports)│ │(scope)  │
    └────┬────┘ └────┬────┘ └────┬────┘
         │           │           │
         └─────┬─────┘           │
               ▼                 │
        ┌────────────┐           │
        │ DiffTracker│◄──────────┘
        │ .calculate │
        │  _impact() │
        └─────┬──────┘
              ▼
        ┌───────────┐    ┌────────────────┐
        │ ImpactSet │───►│ Architect      │
        │ .reanalyze│    │ .generate_plan │
        │ .remove   │    │ (subset only)  │
        └───────────┘    └───────┬────────┘
                                 ▼
                         ┌───────────────┐
                         │ Runner        │
                         │ .run_batch()  │
                         │ (new batches) │
                         └───────┬───────┘
                                 ▼
               ┌─────────────────┼──────────────────┐
               ▼                 ▼                   ▼
        ┌────────────┐  ┌──────────────┐  ┌──────────────────┐
        │ .sense/    │  │ bottom_up/   │  │ state.json       │
        │ (updated)  │  │ (updated)    │  │ (new SHA +       │
        │            │  │              │  │  file_manifest)   │
        └──────┬─────┘  └──────────────┘  └──────────────────┘
               │
               ▼
        ┌──────────────┐
        │ Synthesizer  │
        │ (re-generate │
        │  top_down/)  │
        └──────────────┘
```
