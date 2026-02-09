# Lantern

> **Lighting your way through the code forest.**

[English] | [繁體中文](README_zh-TW.md)

![Lantern Hero Image](assets/lantern.jpg)

**Lantern is your CLI mentor that turns complex repositories into a step-by-step narrative.**

Understand codebases faster with AI-guided architecture scans, planned learning paths, and human-readable guides.

**Speaks Your Language**: Complex logic is hard enough. Lantern explains code in your native language (Chinese, Japanese, Spanish, etc.) while keeping technical terms precise.

### ✨ Highlights

| | |
| :--- | :--- |
| 🧠 **Cognitive Load Reduction** | Psychology-based chunking (Miller's Law) breaks analysis into digestible batches |
| 🌐 **Native Language Output** | Technical docs in your mother tongue—Chinese, Japanese, Spanish, and more |
| 📈 **Flow Reconstruction** | Sequence diagrams showing `request → service → db → response` |
| 💡 **Concept Extraction** | Key mental models: authentication flow, caching strategy, retry mechanisms |
| 📊 **Visual Scaffolding** | Mermaid architecture diagrams + sequence diagrams |
| 🔒 **Local & Private** | CLI-native, no cloud uploads—safe for enterprise codebases |

---

# Why Lantern exists

Understanding a new codebase is hard.

You usually face:
* Not knowing which file to start with.
* Outdated or non-existent documentation.
* Hidden architectural dependencies.
* Needing to read dozens of files to understand one concept.

**The AI Code Problem**

In 2024+, codebases are increasingly filled with AI-generated code that:
* Works, but nobody fully understands *why*
* Lacks meaningful comments or documentation
* Makes legacy code comprehension even harder

Most AI tools help you:
* Write code.
* Refactor code.

**Lantern's goal is different:**
> Lantern helps you **understand** code—whether written by humans or AI.

---

# Use Cases

| Scenario | How Lantern Helps |
| :--- | :--- |
| 👤 **New Hire Onboarding** | Rapidly understand complex legacy systems without tribal knowledge |
| 🔧 **Pre-Refactoring Analysis** | Assess impact scope before making changes |
| ⚠️ **Technical Debt Assessment** | Identify high-risk modules and hidden dependencies |
| 🏗️ **Architecture Decision Support** | Make better design choices with clear system visibility |
| 🔍 **Code Review Preparation** | Understand unfamiliar code before reviewing PRs |

---

# Key Features

### 🧠 Psychology-Driven Design
Not just documentation—**designed for human comprehension**. Chunking, scaffolding, and native language output reduce cognitive load.

### 🔄 Dual-Perspective Analysis
**Bottom-up** (file-by-file details) + **Top-down** (architecture overview) = complete understanding from any angle.

### 🔌 Adaptable Backends
Works with your preferred AI CLI: Codex, Gemini, Claude. Swap backends without changing your workflow.

### ✏️ Human-in-the-Loop
Review and edit `lantern_plan.md` before execution. You control what gets analyzed and how.


# What Lantern Does

**One command. Full documentation.**

```bash
lantern run
```

Lantern analyzes your repository and generates a **complete documentation repository**:

![Lantern Input & Output](assets/input_output.png)

### Input
```
path to repo
```

### Output
```
.lantern/output/
├── en/
│   ├── top_down/                    # 📖 High-level guides
│   │   ├── OVERVIEW.md             # Project vision & scope
│   │   ├── ARCHITECTURE.md         # System design & module relationships
│   │   ├── CONCEPTS.md             # Key concepts (auth flow, caching, retry)
│   │   ├── FLOWS.md                # Critical data flows (Sequence Diagrams)
│   │   └── GETTING_STARTED.md      # Onboarding guide
│   │
│   └── bottom_up/                   # 📝 File-by-file analysis
│       └── src/                     # Mirrors your repo structure
│           ├── kernel/
│           │   ├── scheduler.py.md  # Detailed breakdown
│           │   └── events.py.md
│           └── api/
│               └── routes.py.md
│
└── zh-TW/                           # 🌐 Native language version
    └── (same structure)
```

### How It Maintains Quality

Internally, Lantern uses **batch-based analysis** for quality control:
- Files are analyzed in small batches (1-3 related files)
- Each batch builds on context from previous batches
- This ensures **traceability** and **consistent reasoning**

You don't need to manage this—just run `lantern run` and let it work.

---

# Key Ideas

Lantern is built on psychological design principles:

### Chunking (Miller's Law)
We strictly limit each analysis batch to ~3 related files to prevent cognitive information overload.

### Scaffolding
By generating a plan first and allowing for human review, we build a steady ladder for understanding complex systems.

### Human-First Output
Final outputs are designed for human reading, not machine consumption, focusing on "Why" and "How" rather than just "What".

---

# Quick Start

## Prerequisites

Lantern requires one of the following AI CLI tools installed:

| CLI Tool | Installation |
| :--- | :--- |
| **Codex CLI** | `npm install -g @openai/codex` |
| **Gemini CLI** | `npm install -g @anthropic/gemini-cli` |
| **Claude Code** | `npm install -g @anthropic/claude-code` |

Lantern auto-detects available CLI backends.

## Installation

```bash
pip install lantern-cli
```

## Simple Mode (Recommended)

```bash
# Run in current directory (outputs to .lantern/)
lantern run

# Specify input and output
lantern run --repo ~/projects/my-app --output ~/docs/my-app-docs
```

Lantern auto-detects available CLI backends: `codex` → `gemini` → `claude`

## Advanced Mode

For reviewing the analysis plan before execution:

```bash
# Step 1: Initialize
lantern init --repo /path/to/repo

# Step 2: Generate plan (review lantern_plan.md)
lantern plan

# Step 3: Execute analysis
lantern run
```

## Specify Backend

```bash
lantern run --backend claude
lantern run --backend gemini
```

---

# Real Example

Analyzing [accellera-official/systemc](https://github.com/accellera-official/systemc):

**Top-down output** (`ARCHITECTURE.md`):
> SystemC is effectively a **co-operative multitasking OS** specialized for hardware simulation.
> At its core lies the `sc_simcontext`, which acts as the kernel, scheduler, and event manager.

**Bottom-up output** (`sc_simcontext.md`):
> `sc_simcontext` is the **central nervous system** of the SystemC simulation kernel.
> It manages: Global Simulation State, Object Registry, Scheduler, Process Management.

---

# Example: Lantern Analyzes Itself

Here is a summary of the architecture report generated by Lantern analyzing its own codebase (`lantern-cli`):

### [Generated] Project Overview

**Lantern CLI** is a Python-based command-line tool designed to help developers rapidly understand unfamiliar codebases.

#### Core Architecture
The system uses a **Pipeline Pattern**, consisting of the following primary modules:

1.  **CLI Layer (`src/lantern_cli/cli`)**
    -   Uses the `Typer` framework to handle command-line inputs (`main.py`).
    -   Orchestrates the execution flow of `init`, `plan`, and `run` commands.

2.  **Core Layer (`src/lantern_cli/core`)**
    -   **Architect (`architect.py`)**: Acts as the planner, analyzing the `DependencyGraph` and generating a batched analysis plan (`lantern_plan.md`).
    -   **Runner (`runner.py`)**: Acts as the executor, communicating with LLM backends, executing batch analysis, and handling state persistence (`StateManager`) for resume capability.
    -   **Synthesizer (`synthesizer.py`)**: Acts as the synthesizer, aggregating scattered batch analysis results (`.sense` files) into final Top-down documentation.

3.  **Backend Adapter Layer (`src/lantern_cli/backends`)**
    -   Implements the Strategy Pattern via `BackendFactory`.
    -   Supports multiple LLM backends: `CodexAdapter`, `GeminiAdapter`, `ClaudeAdapter`.
    -   Abstracts away the invocation details of different CLI tools.

---

# Configuration

## Language settings

You can set your preferred output language (e.g., Traditional Chinese, Japanese) to lower the cognitive barrier even further.

**Option A: Command line**
```bash
lantern run --lang zh-TW
```

---

# Supported Agents

Lantern drives your favorite CLI agents:
* Claude Code
* Gemini CLI (Antigravity)
* Open-source local runners

---

# Roadmap

- [ ] **Execution Trace Mode**: Collect call graphs via unit tests for dynamic analysis.
- [ ] **Memory Cross-talk**: Enhanced reasoning across batch boundaries.
- [ ] **Multi-language Static Analysis**: Go, Rust, and Java support.
- [ ] **VSCode Extension**: Integrated progress tracking.

---

# Contributing

PRs are welcome! Help us build the ultimate tool for code understanding.

---

# License

MIT
