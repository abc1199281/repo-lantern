# Lantern

> **Illuminating unfamiliar codebases.**

[English] | [繁體中文](README_zh-TW.md)

![Lantern Hero Image](assets/lantern.jpg)

**Lantern is your CLI mentor that turns complex repositories into a step-by-step narrative.**

Understand codebases faster with AI-guided architecture scans, planned learning paths, and human-readable guides.

**Speaks Your Language**: Complex logic is hard enough. Lantern explains code in your native language (Chinese, Japanese, Spanish, etc.) while keeping technical terms precise.

---

# Why Lantern exists

Understanding a new codebase is hard.

You usually face:
* Not knowing which file to start with.
* Outdated or non-existent documentation.
* Hidden architectural dependencies.
* Needing to read dozens of files to understand one concept.

Most AI tools help you:
* Write code.
* Refactor code.

**Lantern's goal is different:**
> Lantern helps you **understand** code.

---

# What Lantern does

Lantern follows a structured "cognition-first" workflow:

1. **Scan**: Maps out the repository structure and dependencies.
2. **Chunk**: Breaks analysis into small, manageable batches (1-3 files).
3. **Step-by-step**: Guides you through core modules one by one.
4. **Synthesize**: Produces human-readable documentation with both bottom-up (file-level) and top-down (architectural) views.

---

# How Lantern works

![How Lantern works](assets/latern-2.jpg)

Lantern uses a phased pedagogical approach:

```bash
Init (Input repo)
   ↓
Static Scan (Analyze dependencies)
   ↓
Orchestration (Generate Lantern Plan)
   ↓
Execution (Iterative Batch Analysis)
   ↓
Synthesis (High-level guides)
```

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

## Installation

```bash
pip install lantern-cli
```

## Basic Usage

1. **Initialize**: Point Lantern to a repository.
   ```bash
   lantern init <repo_url_or_path>
   ```

2. **Plan**: Generate the analysis orchestration.
   ```bash
   lantern plan
   ```

3. **Run**: Execute the step-by-step analysis.
   ```bash
   lantern run
   ```

---

# Example Output

```markdown
# Phase 2: API Layer

The API layer is built with FastAPI.

Authentication flow:
client → middleware → JWT verification → route handler

Key insight:
Business logic is separated from HTTP transport.
```

---

# Configuration

## Language settings

You can set your preferred output language (e.g., Traditional Chinese, Japanese) to lower the cognitive barrier even further.

**Option A: Command line**
```bash
lantern run --lang zh-TW
```

**Option B: Config file (`lantern.toml`)**
```toml
[lantern]
language = "zh-TW"
```

---

# Supported Agents

Lantern drives your favorite CLI agents:
* Claude Code
* Gemini CLI (Antigravity)
* Open-source local runners

---

# Roadmap

- [ ] **Interactive Quiz Mode**: Test your understanding after each phase.
- [ ] **Visual Scaffolding**: Automatic architecture diagrams using Mermaid.js.
- [ ] **Memory Cross-talk**: Enhanced reasoning across batch boundaries.
- [ ] **Multi-language Static Analysis**: Go, Rust, and Java support.
- [ ] **VSCode Extension**: Integrated progress tracking.

---

# Contributing

PRs are welcome! Help us build the ultimate tool for code understanding.

---

# License

MIT