# LangGraph Architecture Design

This document describes the LangGraph StateGraph designs used in Lantern CLI.
All diagrams use Mermaid syntax (rendered natively by GitHub).

---

## A. Main Workflow Graph

The primary orchestration graph in `core/workflow.py`. It has **7 nodes** and
**2 conditional routers** (human review and quality gate).

```mermaid
stateDiagram-v2
    [*] --> static_analysis
    static_analysis --> planning
    planning --> human_review

    state human_review_fork <<choice>>
    human_review --> human_review_fork
    human_review_fork --> batch_execution : approved
    human_review_fork --> planning : rejected
    human_review_fork --> human_review : waiting

    batch_execution --> synthesis
    synthesis --> quality_gate

    state quality_gate_fork <<choice>>
    quality_gate --> quality_gate_fork
    quality_gate_fork --> [*] : pass
    quality_gate_fork --> refine : fail & iter < 3
    quality_gate_fork --> [*] : fail & iter >= 3

    refine --> quality_gate
```

### Node Summary

| Node | Source | Responsibility |
|------|--------|----------------|
| `static_analysis` | `workflow.py` | Build dependency graph, calculate layers, generate Mermaid |
| `planning` | `workflow.py` | Generate `Plan` (static or agentic mode) |
| `human_review` | `workflow.py` | Interrupt for plan approval; auto-approves with `--yes` |
| `batch_execution` | `workflow.py` | Process batches via `Runner` with `EnhancedContextManager` |
| `synthesis` | `workflow.py` | Generate top-down docs (batch or agentic mode) |
| `quality_gate` | `workflow.py` | Evaluate synthesis quality score against 0.8 threshold |
| `refine` | `workflow.py` | Bump quality score and loop back (max 3 iterations) |

### Conditional Routers

- **`router_human_review`** — routes to `batch_execution` (approved), `planning` (rejected), or `human_review` (waiting for input).
- **`router_quality_gate`** — routes to `END` (quality >= 0.8 or max iterations reached) or `refine` (quality < 0.8 and iterations < 3).

### State

`LanternWorkflowState` (TypedDict) carries all data across nodes: input
parameters, static analysis results, plan, batch execution records, synthesis
documents, quality metrics, and iteration count.

---

## B. Agentic Planner Sub-Graph

A 4-node linear sub-graph in `core/agentic_planner.py`. Used when
`--planning-mode agentic` is set. Each node invokes the LLM to progressively
build understanding of the codebase for smarter file grouping.

```mermaid
graph LR
    START((__START__)) --> analyze_structure
    analyze_structure --> identify_patterns
    identify_patterns --> semantic_grouping
    semantic_grouping --> generate_hints
    generate_hints --> END_((__END__))
```

### Node Summary

| Node | Input | Output |
|------|-------|--------|
| `analyze_structure` | file tree, dependencies, layers, sampled file contents | `structure_analysis` (free-text) |
| `identify_patterns` | `structure_analysis`, sampled contents, dependencies | `patterns_analysis` (free-text) |
| `semantic_grouping` | file list, `patterns_analysis`, dependencies, layers | `semantic_groups_json` (JSON array of file groups) |
| `generate_hints` | semantic groups, `patterns_analysis`, `structure_analysis` | `batch_hints_json` (JSON map: batch index -> hint) |

### State

`PlanningState` (TypedDict) contains input data (file tree, dependency summary,
layer summary, sampled contents) and LLM-generated intermediate results.

---

## C. Agentic Synthesizer Sub-Graph

A 6-node linear sub-graph in `core/agentic_synthesizer.py`. Used when
`--synthesis-mode agentic` is set. Each node builds on prior analysis to
produce richer documentation.

```mermaid
graph LR
    START((__START__)) --> identify_patterns
    identify_patterns --> cross_compare
    cross_compare --> generate_overview
    generate_overview --> generate_architecture
    generate_architecture --> generate_getting_started
    generate_getting_started --> generate_concepts
    generate_concepts --> END_((__END__))
```

### Node Summary

| Node | Input | Output |
|------|-------|--------|
| `identify_patterns` | sense records | `patterns_analysis` |
| `cross_compare` | `patterns_analysis`, sense records | `cross_comparison` |
| `generate_overview` | `patterns_analysis`, `cross_comparison`, sense records | `overview_doc` (OVERVIEW.md) |
| `generate_architecture` | `patterns_analysis`, `cross_comparison`, dependency Mermaid, file details | `architecture_doc` (ARCHITECTURE.md) |
| `generate_getting_started` | `overview_doc`, `patterns_analysis`, functions, entry points | `getting_started_doc` (GETTING_STARTED.md) |
| `generate_concepts` | `patterns_analysis`, `cross_comparison`, classes summary | `concepts_doc` (CONCEPTS.md) |

### State

`SynthesisState` (TypedDict) contains sense records, plan content, dependency
Mermaid, and the progressively generated documents.

---

## D. End-to-End Sequence: `lantern run --workflow`

Shows the interaction between CLI, workflow executor, graph nodes, and LLM
backend during a complete run, including checkpoint/resume.

```mermaid
sequenceDiagram
    participant User
    participant CLI as CLI (main.py)
    participant Exec as WorkflowExecutor
    participant WF as StateGraph
    participant SA as static_analysis
    participant PL as planning
    participant HR as human_review
    participant BE as batch_execution
    participant SY as synthesis
    participant QG as quality_gate
    participant RF as refine
    participant LLM as Backend
    participant CP as Checkpointer

    User->>CLI: lantern run --workflow
    CLI->>Exec: LanternWorkflowExecutor(repo, backend, config)
    Exec->>WF: invoke(initial_state, thread_id)
    WF->>CP: save checkpoint (initial)

    WF->>SA: static_analysis_node(state)
    SA-->>WF: dependency_graph, layers, mermaid
    WF->>CP: save checkpoint

    WF->>PL: planning_node(state)
    PL-->>WF: plan, pending_batches
    WF->>CP: save checkpoint

    WF->>HR: human_review_node(state)
    alt --yes flag or no interrupt
        HR-->>WF: plan_approved = true
    else rejected
        HR-->>WF: plan_rejected = true
        WF->>PL: loop back to planning
    end
    WF->>CP: save checkpoint

    WF->>BE: batch_execution_node(state, backend, runner)
    loop each batch
        BE->>LLM: invoke / invoke_structured
        LLM-->>BE: analysis results
    end
    BE-->>WF: completed_batches, sense_records
    WF->>CP: save checkpoint

    WF->>SY: synthesis_node(state, backend)
    SY->>LLM: generate docs (batch or agentic)
    LLM-->>SY: OVERVIEW, ARCHITECTURE, CONCEPTS, GETTING_STARTED
    SY-->>WF: documents, quality_score
    WF->>CP: save checkpoint

    WF->>QG: quality_gate_node(state)
    alt quality >= 0.8
        QG-->>WF: quality_ok = true
        WF-->>Exec: final state
    else quality < 0.8 & iter < 3
        QG-->>WF: quality_ok = false
        WF->>RF: refine_node(state)
        RF-->>WF: improved documents
        WF->>QG: loop back
    end
    WF->>CP: save checkpoint (final)

    Exec-->>CLI: final state
    CLI-->>User: done

    Note over User,CLI: Resume with --resume <thread-id>
    User->>CLI: lantern run --workflow --resume abc123
    CLI->>Exec: LanternWorkflowExecutor(...)
    Exec->>WF: invoke(state, thread_id="abc123")
    WF->>CP: restore checkpoint
    Note over WF: resumes from last saved node
```

---

## Key Design Decisions

1. **Checkpointing** — Every node transition is checkpointed via LangGraph's
   `MemorySaver` (default) or `SqliteSaver` (when a checkpoint directory is
   configured). This enables `--resume <thread-id>`.

2. **Human-in-the-loop** — `human_review` supports plan approval/rejection.
   Currently auto-approves when `--yes` is set or no interrupt mechanism is
   configured.

3. **Quality loop** — The `quality_gate -> refine -> quality_gate` cycle runs
   up to 3 iterations, incrementally improving synthesis quality.

4. **Sub-graph isolation** — The agentic planner and synthesizer are compiled
   as independent `StateGraph` instances. They are invoked within the main
   workflow's `planning_node` and `synthesis_node` respectively, keeping
   concerns separated.

5. **Backend protocol** — All LLM calls go through the `Backend` protocol
   (`llm/backend.py`), keeping provider-specific code isolated in
   `llm/backends/`.
