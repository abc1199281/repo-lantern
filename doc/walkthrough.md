# Lantern CLI Walkthrough

This document demonstrates how to use the newly implemented Lantern CLI to analyze a repository.

## Installation

Ensure you are in the project root and have dependencies installed:

```bash
# Install dependencies
pip install lantern-cli

# Or for development
poetry install
poetry shell
```

## 1. Initialize Lantern

Start by initializing Lantern validation in your repository. This creates the `.lantern` directory and a default configuration file.

```bash
lantern init
```

**Output:**
```
Initialized Lantern in /path/to/repo/.lantern
Configuration created at: /path/to/repo/.lantern/lantern.toml
```

You can customize `lantern.toml` to adjust settings like language or file filters.

## 2. Generate Analysis Plan (Optional)

If you want to see what Lantern plans to do before running the full analysis, use the `plan` command. This uses static analysis to map dependencies and organize files into batches.

```bash
lantern plan
```

**Output:**
```
lantern_plan.md generated.
```

Review `.lantern/lantern_plan.md` to see the proposed analysis phases.

## 3. Run Analysis

Execute the full analysis pipeline. This will:
1.  Build the dependency graph
2.  Generate/Load the plan
3.  Execute analysis batches using the configured backend (e.g., Gemini, Claude)
4.  Generate bottom-up documentation for each file
5.  Synthesize top-down documentation (Overview, Architecture, etc.)

```bash
# Run with default settings (CLI backend)
lantern run

# Run with specific backend
lantern run --backend gemini
```

**Output:**
```
Lantern Analysis
Repository: ...
Backend: api (gemini)
...
Analysis Complete!
Documentation available in: .lantern/
```

## 4. View Documentation

Generated documentation can be found in `.lantern/output/en/`:

*   **Top-Down:**
    *   `OVERVIEW.md`: High-level project summary
    *   `ARCHITECTURE.md`: System design and modules
    *   `GETTING_STARTED.md`: Onboarding guide
    *   `CONCEPTS.md`: Key concepts
*   **Bottom-Up:**
    *   `bottom_up/src/...`: Detailed analysis for each source file

## Integration Tests

We have added an end-to-end integration test suite to verify the CLI flow.

```bash
pytest tests/integration/test_cli_flow.py -v
```
