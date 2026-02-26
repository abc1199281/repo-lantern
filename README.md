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
| 📊 **Auto-Generated Diagrams** | Mermaid flowcharts + sequence diagrams automatically created for every module |
| 💡 **Concept Extraction** | Key mental models: authentication flow, caching strategy, retry mechanisms |
|  **Local & Private** | Supports Ollama for 100% local analysis—safe for enterprise codebases |

---

# Why Lantern exists

Understanding a new codebase is hard. You face:
* Not knowing which file to start with
* Outdated or missing documentation
* Hidden architectural dependencies
* Needing to read dozens of files to understand one concept

**Modern codebases often contain AI-generated code that works but lacks documentation**—making comprehension even harder.

Most AI tools help you *write* or *refactor* code. **Lantern's goal is different:**
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

# Core Design & Features

### 🧠 Psychology-Driven Design
**Designed for human comprehension**, not machines. Lantern uses psychological principles:
- **Chunking** (Miller's Law): Analyzes batches of ~3 related files to prevent cognitive overload
- **Scaffolding**: Generates a plan first for human review, building understanding step-by-step
- **Human-First Output**: Explains "Why" and "How", focusing on comprehension over data

### 🔄 Dual-Perspective Analysis
**Bottom-up** (file-by-file details) + **Top-down** (architecture overview) = complete understanding from any angle.

### 🔌 Flexible Backends
Choose between local privacy (Ollama), cloud power (OpenRouter/OpenAI), or agent-based workflows (CLI tools). Lantern automatically detects backend type and uses the appropriate analysis workflow.

### 🤖 Agentic Modes
Independently upgrade the planning and synthesis stages to LLM-powered agents:
- **`--planning-mode agentic`**: Uses `AgenticPlanner` to generate LLM-enhanced batch hints and learning objectives on top of the static dependency graph.
- **`--synthesis-mode agentic`**: Uses `AgenticSynthesizer` (LangGraph) to write Markdown documentation files directly via file tools instead of structured JSON parsing.

### 🔁 LangGraph Workflow Orchestration
Use `--workflow` to run the full pipeline as a LangGraph `StateGraph` with checkpoint-based resumption:
- Enables **pause and resume** via `--resume <thread-id>`
- Conditional routing based on quality gates
- Human-in-the-loop interrupt support

### 📄 Spec-Aware Documentation
Enrich generated docs with design intent from specification documents:
- `lantern spec add spec.pdf` — LLM auto-maps specs to code modules
- Supports PDF (with table extraction) and Markdown
- Spec context is injected into analysis, planning, and synthesis prompts
- Mappings stored in `.lantern/specs.toml` — fully editable

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
│   │   ├── ARCHITECTURE.md         # System design + Mermaid dependency graphs
│   │   ├── CONCEPTS.md             # Key concepts (auth flow, caching, retry)
│   │   └── GETTING_STARTED.md      # Onboarding guide + Mermaid sequence diagrams
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

# Visual Flow Reconstruction

Lantern automatically generates **Mermaid diagrams** for every analyzed file:

### Architecture Diagrams
Show module dependencies in `ARCHITECTURE.md`:

```mermaid
graph LR
    API --> Auth
    API --> Models
    Auth --> Database
    Models --> Database
```

**Sequence Diagrams & Per-File Flows**: Lantern also generates request/response sequence diagrams and per-file flow diagrams showing internal logic.

**No manual work needed**—diagrams are generated automatically by analyzing your code structure.

---

# Quick Start

## Prerequisites

Lantern supports multiple backend options. See [Backend Configuration](#backend-configuration) for detailed setup instructions:

- **OpenAI** (Recommended) - Cost-effective, production-ready
- **Ollama** (Free & Private) - Run locally without API calls
- **OpenRouter** - Access multiple providers (Claude, Gemini, etc.)
- **CLI Tool** - Leverage agent capabilities (file tools, code execution)

## Installation

```bash
pip install repo-lantern
```

## Simple Mode (Recommended)

```bash
# Run in current directory (outputs to .lantern/)
lantern run

# Specify input and output
lantern run --repo ~/projects/my-app --output ~/docs/my-app-docs

# Use specific language
lantern run --lang zh-TW  # Traditional Chinese

# Skip the confirmation prompt
lantern run --yes

# Incrementally update after code changes
lantern update

# Skip confirmation
lantern update --yes

# Set up AI coding tool instructions (Codex, Copilot, Claude)
lantern onboard
lantern onboard --tools codex --tools claude   # Specific tools only
lantern onboard --overwrite                     # Replace existing sections

# Associate spec documents with code for richer documentation
lantern spec add path/to/auth-spec.pdf        # Auto-maps spec to modules via LLM
lantern spec list                              # Show all spec mappings
lantern spec remove auth-spec                  # Remove a spec mapping
```

The default backend is OpenAI, but you can configure it in `.lantern/lantern.toml`:

```toml
[backend]
type = "openai"              # or "ollama", "openrouter"
openai_model = "gpt-4o-mini" # fast and cheap for production
# openai_model = "gpt-4o"    # higher quality option
```

## Advanced Mode

For reviewing the analysis plan before execution:

```bash
# Step 1: Initialize (creates .lantern/lantern.toml)
lantern init --repo /path/to/repo
# Initialize with custom output directory
lantern init --repo /path/to/repo --output my-docs
# Re-initialize and overwrite existing config
lantern init --repo /path/to/repo --overwrite

# Step 2: Generate plan (review lantern_plan.md)
lantern plan
lantern plan --planning-mode static   # Use topological sort instead of LLM

# Step 3: Execute analysis with optional flags
lantern run
lantern run --planning-mode static    # Topological planning (no LLM)
lantern run --synthesis-mode batch    # Rule-based synthesis (no LLM)
lantern run --no-workflow             # Disable LangGraph orchestration
lantern run --resume <thread-id>     # Resume from checkpoint
```

### All `lantern init` Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--repo` | `.` | Repository path |
| `--output` | `.lantern` | Output directory (written to config) |
| `--overwrite` / `-f` | false | Force re-initialization |

### All `lantern plan` Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--repo` | `.` | Repository path |
| `--output` | `.lantern` | Output directory |
| `--lang` | `en` | Output language (e.g., `zh-TW`, `ja`) |
| `--planning-mode` | `agentic` | `static` (topological) or `agentic` (LLM-enhanced) |

### All `lantern run` Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--repo` | `.` | Repository path to analyze |
| `--output` | `.lantern` | Output directory |
| `--lang` | `en` | Output language (e.g., `zh-TW`, `ja`) |
| `--yes` / `-y` | false | Skip confirmation prompt |
| `--planning-mode` | `agentic` | `static` (topological) or `agentic` (LLM-enhanced) |
| `--synthesis-mode` | `agentic` | `batch` (rule-based) or `agentic` (LLM-powered) |
| `--workflow` | true | Use LangGraph workflow orchestration |
| `--resume` | — | Resume from checkpoint with given thread ID |

### All `lantern onboard` Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--repo` | `.` | Repository path |
| `--tools` | `codex, copilot, claude` | Target tools to generate instructions for |
| `--overwrite` / `-f` | false | Replace existing lantern section in target files |

Writes Lantern skill instructions to tool-specific files:
- **Codex** → `AGENTS.md`
- **Copilot** → `.github/copilot-instructions.md`
- **Claude** → `CLAUDE.md`

### All `lantern update` Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--repo` | `.` | Repository path |
| `--output` | `.lantern` | Output directory |
| `--lang` | `en` | Output language (e.g., `zh-TW`, `ja`) |
| `--yes` / `-y` | false | Skip confirmation prompt |
| `--synthesis-mode` | `agentic` | `batch` (rule-based) or `agentic` (LLM-powered) |

### All `lantern spec` Subcommands

| Command | Description |
| :--- | :--- |
| `lantern spec add <file>` | Add a spec file (PDF/MD), auto-map to modules via LLM, generate summary |
| `lantern spec list` | List all spec-to-module mappings from `.lantern/specs.toml` |
| `lantern spec remove <name>` | Remove a spec entry (and optionally its files) |

# Configuration

## Language settings

You can set your preferred output language (e.g., Traditional Chinese, Japanese) to lower the cognitive barrier even further.

**Option A: Command line**
```bash
lantern run --lang zh-TW
```

## LangSmith Observability (Optional)

Lantern integrates with [LangSmith](https://smith.langchain.com/) for tracing and debugging LLM calls across the entire pipeline.

Enable it in `.lantern/lantern.toml`:
```toml
[langsmith]
enabled = true
project = "repo-lantern"            # Project name in LangSmith dashboard
# endpoint = "https://api.smith.langchain.com"
# api_key_env = "LANGCHAIN_API_KEY"
```

Set your API key:
```bash
export LANGCHAIN_API_KEY="ls__..."
```

When enabled, Lantern prints `LangSmith tracing: ON (project=repo-lantern)` at startup and all LangChain/LangGraph calls are traced.

---

# Backend Configuration

Lantern supports multiple LLM backends with easy configuration:

### OpenAI (Recommended for Production) ⭐
```toml
# .lantern/lantern.toml
[backend]
type = "openai"
openai_model = "gpt-4o-mini"  # Fast and cheap
# openai_model = "gpt-4o"     # Higher quality
```

Set your API key:
```bash
export OPENAI_API_KEY="sk-..."
```

### Ollama (Local Models)
```toml
[backend]
type = "ollama"
ollama_model = "qwen2.5:14b"  # or llama3, mistral, etc.
```

### OpenRouter (Multi-Model Access)
```toml
[backend]
type = "openrouter"
openrouter_model = "openai/gpt-4o-mini"  # or anthropic/claude-sonnet-4, etc.
```

Set your API key:
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

### CLI Tool (Agent-Based Workflow) 🤖
```toml
[backend]
type = "cli"
cli_command = "codex exec"  # or "llm -m gpt-4o-mini", "claude", etc.
cli_model_name = "cli"
```

**How it works**:
- Lantern detects CLI backends and automatically switches to **agent-based workflow**
- Prompts instruct the agent to write Markdown files directly using file tools
- Agents leverage their native capabilities (code execution, file operations, etc.)
- No JSON parsing required - agents write documentation files directly

**Supported CLI tools**:
- `codex exec` - OpenAI Codex with agent capabilities
- `llm -m <model>` - Simon Willison's LLM tool
- `claude` - Anthropic Claude CLI
- Any custom CLI that accepts stdin and outputs to stdout

**Example workflow**:
```bash
# Install a CLI tool (example: llm)
pip install llm

# Configure Lantern to use it
echo '[backend]
type = "cli"
cli_command = "llm -m gpt-4o-mini"
cli_model_name = "gpt-4o-mini"' > .lantern/lantern.toml

# Run analysis
lantern run
```

---

# Roadmap

- [x] **LangGraph Workflow Orchestration**: Full StateGraph with checkpoint-based resumption (`--workflow`, `--resume`).
- [x] **Agentic Planning & Synthesis**: LLM-enhanced planning (`--planning-mode agentic`) and synthesis (`--synthesis-mode agentic`).
- [x] **LangSmith Observability**: Tracing integration for debugging LLM calls.
- [x] **Incremental Update**: Git diff-based `lantern update` command for re-analyzing only changed files.
- [x] **Spec-Aware Documentation**: Associate specification documents (PDF/MD) with code modules for richer, design-intent-aware documentation.
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
