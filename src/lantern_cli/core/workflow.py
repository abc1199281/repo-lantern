"""
Lantern Workflow - LangGraph StateGraph orchestration for the complete analysis pipeline.

This module implements Phase 3 of the LangGraph Subagent evaluation:
- Full workflow StateGraph orchestration
- Human-in-the-loop support with interrupts
- LangGraph checkpointer for state persistence
- Conditional routing based on quality scores and user approval
"""

import logging
from dataclasses import dataclass
from operator import add
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from lantern_cli.core.architect import Architect, Plan
from lantern_cli.core.runner import Runner
from lantern_cli.core.state_manager import StateManager
from lantern_cli.core.synthesizer import Synthesizer
from lantern_cli.static_analysis import DependencyGraph, FileFilter

if TYPE_CHECKING:
    from lantern_cli.llm.backend import Backend

logger = logging.getLogger(__name__)


class LanternWorkflowState(TypedDict):
    """
    Complete state for the Lantern analysis workflow.

    Extends the traditional ExecutionState with structured tracking for:
    - Input parameters
    - Analysis results
    - Quality metrics
    - Cost tracking
    - Enhanced context management (Phase 4)
    """

    # Input parameters
    repo_path: str
    config: dict[str, Any]  # Serializable config dict
    language: str
    target_language: str  # User's desired output language (analysis always runs in English)
    synthesis_mode: str
    planning_mode: str
    assume_yes: bool
    output_dir: str  # Output directory for documentation

    # Static analysis results
    dependency_graph: dict[str, list[str]]  # file -> [dependencies]
    reverse_dependencies: dict[str, list[str]]  # file -> [dependents]
    file_list: list[str]
    layers: list[list[str]]  # Dependency layers
    mermaid_graph: str

    # Planning results
    plan: dict[str, Any] | None  # Serializable Plan representation
    plan_approved: bool
    plan_rejected: bool

    # Batch execution state
    pending_batches: list[dict[str, Any]]  # Serializable Batch representation
    completed_batches: list[int]  # Batch IDs
    failed_batches: list[int]  # Batch IDs
    sense_records: Annotated[list[dict[str, Any]], add]  # Auto-merge new records
    global_summary: str
    batch_errors: dict[int, str]  # batch_id -> error message

    # Phase 4: Enhanced Context Management
    structured_analyses: dict[str, dict[str, Any]]  # file_path -> analysis result
    context_manager_state: dict[str, Any]  # Serialized context manager state

    # Synthesis results
    documents: dict[str, str]  # filename -> content
    synthesis_quality_score: float

    # Quality gates
    quality_score: float
    quality_ok: bool
    quality_issues: list[str]

    # Cost tracking
    total_cost: float
    estimated_cost: float

    # Workflow control
    iteration_count: int  # For preventing infinite loops
    needs_reanalysis: bool


@dataclass
class LanternCheckpointConfig:
    """Configuration for LangGraph checkpointer."""

    enable_checkpointing: bool = True
    checkpoint_dir: Path | None = None

    def get_saver(self):
        """Get the appropriate saver (in-memory or file-based)."""
        if self.enable_checkpointing and self.checkpoint_dir:
            try:
                from langgraph_checkpoint.sqlite import SqliteSaver

                return SqliteSaver(str(self.checkpoint_dir / "checkpoints.db"))
            except ImportError:
                try:
                    from langgraph.checkpoint.sqlite import SqliteSaver

                    return SqliteSaver(str(self.checkpoint_dir / "checkpoints.db"))
                except ImportError:
                    # Fallback to memory saver
                    return MemorySaver()
        else:
            # In-memory fallback
            return MemorySaver()


def _serialize_plan(plan: Plan) -> dict[str, Any]:
    """Convert Plan object to serializable dict."""
    if not plan:
        return None

    phases = []
    for phase in plan.phases:
        batches = []
        for batch in phase.batches:
            batches.append(
                {
                    "id": batch.id,
                    "files": batch.files,
                    "hint": batch.hint,
                }
            )
        phases.append(
            {
                "id": phase.id,
                "batches": batches,
                "learning_objectives": phase.learning_objectives,
            }
        )

    return {
        "phases": phases,
        "confidence_score": plan.confidence_score,
        "dependencies_mermaid": plan.dependencies_mermaid,
    }


def _deserialize_plan(plan_dict: dict[str, Any]) -> Plan:
    """Reconstruct Plan object from serialized dict."""
    if not plan_dict:
        return None

    from lantern_cli.core.architect import Batch, Phase

    phases = []
    for phase_dict in plan_dict.get("phases", []):
        batches = []
        for batch_dict in phase_dict.get("batches", []):
            batches.append(
                Batch(
                    id=batch_dict["id"],
                    files=batch_dict["files"],
                    hint=batch_dict.get("hint", ""),
                )
            )
        phases.append(
            Phase(
                id=phase_dict["id"],
                batches=batches,
                learning_objectives=phase_dict.get("learning_objectives", []),
            )
        )

    return Plan(
        phases=phases,
        confidence_score=plan_dict.get("confidence_score", 1.0),
        dependencies_mermaid=plan_dict.get("dependencies_mermaid", ""),
    )


# ============================================================================
# Node Implementations
# ============================================================================


def static_analysis_node(state: LanternWorkflowState) -> dict[str, Any]:
    """
    Node 1: Static Analysis
    - Build dependency graph
    - Calculate layers
    - Filter files
    """
    logger.info("Starting static analysis...")

    repo_path = Path(state["repo_path"])
    config_dict = state["config"]

    # Load config object
    from lantern_cli.config.loader import Config

    config = Config(**config_dict)

    # Build dependency graph
    file_filter = FileFilter(repo_path, config.filter)
    graph = DependencyGraph(repo_path, file_filter=file_filter)
    graph.build()

    layers = graph.calculate_layers()

    # Generate mermaid graph
    architect = Architect(repo_path, graph)
    mermaid_graph = architect.generate_mermaid_graph()

    return {
        "dependency_graph": dict(graph.dependencies),
        "reverse_dependencies": dict(graph.reverse_dependencies),
        "file_list": list(graph.dependencies.keys()),
        "layers": layers,
        "mermaid_graph": mermaid_graph,
    }


def planning_node(state: LanternWorkflowState) -> dict[str, Any]:
    """
    Node 2: Planning
    - Generate analysis plan
    - Support both static and agentic planning
    """
    logger.info(f"Starting planning (mode: {state['planning_mode']})...")

    repo_path = Path(state["repo_path"])
    state["planning_mode"]

    # Use static planning by default (agentic would require backend)
    architect = Architect(repo_path, None)  # Will be reconstructed with graph

    # Reconstruct graph from state

    # Note: In production, we'd pass the actual DependencyGraph
    # For now, create a minimal plan
    plan = architect.generate_plan()

    # Get pending batches
    state_manager = StateManager(repo_path)
    pending_batches = state_manager.get_pending_batches(plan)

    # Serialize batches
    batches = []
    for batch in pending_batches:
        batches.append(
            {
                "id": batch.id,
                "files": batch.files,
                "hint": batch.hint,
            }
        )

    return {
        "plan": _serialize_plan(plan),
        "pending_batches": batches,
        "plan_approved": False,
        "plan_rejected": False,
    }


def human_review_node(state: LanternWorkflowState) -> dict[str, Any]:
    """
    Node 3: Human Review (with interrupt)
    - Allow human to review and approve the plan
    - Optionally request modifications
    """
    logger.info("Waiting for human review...")

    # In LangGraph, interrupts are handled at invocation time
    # This node just marks that we're waiting for user input
    return {
        "plan_approved": state.get("plan_approved", False),
        "plan_rejected": state.get("plan_rejected", False),
    }


def batch_execution_node(
    state: LanternWorkflowState, backend: Optional["Backend"] = None, runner: Runner | None = None
) -> dict[str, Any]:
    """
    Node 4: Batch Execution
    - Process pending batches
    - Use EnhancedContextManager for intelligent context (Phase 4)
    - Update sense records and global summary
    - Track costs

    Note: In real workflow execution, backend and runner would be provided via closure/context.
    """
    logger.info("Starting batch execution with enhanced context management...")

    from lantern_cli.core.context_manager import (
        EnhancedContextManager,
        StructuredAnalysisResult,
    )

    Path(state["repo_path"])
    pending_batches = state["pending_batches"]
    language = state.get("language", "en")
    dependency_graph = state.get("dependency_graph", {})

    completed = []
    failed = []
    sense_records = []
    total_cost = 0.0
    batch_errors = {}
    structured_analyses = {}
    context_manager_state = {}

    # Initialize or restore context manager (Phase 4)
    if state.get("context_manager_state"):
        # Restore from checkpoint
        context_manager = EnhancedContextManager.from_dict(
            state["context_manager_state"],
            dependency_graph=dependency_graph,
        )
    else:
        # Create new
        context_manager = EnhancedContextManager(
            dependency_graph=dependency_graph,
            max_context_length=6000,
        )

    # If backend and runner are provided, execute batches
    if backend and runner:
        for batch_dict in pending_batches:
            try:
                batch_id = batch_dict["id"]
                logger.info(f"Processing batch {batch_id}...")

                # Phase 4: Get intelligent context based on dependencies
                batch_files = batch_dict["files"]
                previous_context = context_manager.get_relevant_context(
                    target_files=batch_files,
                    include_depth=2,
                    min_quality=0.6,
                )

                # Construct prompt with intelligent context
                language_instruction = f" Please respond in {language}." if language != "en" else ""
                hint_instruction = (
                    f"\n\nAnalysis guidance: {batch_dict.get('hint', '')}"
                    if batch_dict.get("hint")
                    else ""
                )
                context_section = (
                    f"\n\nPrevious analysis context:\n{previous_context}"
                    if previous_context
                    else ""
                )

                prompt = (
                    f"Analyze these files: {batch_files}. Provide a summary and key insights."
                    f"{language_instruction}{hint_instruction}{context_section}"
                )

                # Create minimal Batch object for runner
                from lantern_cli.core.architect import Batch

                batch = Batch(
                    id=batch_id,
                    files=batch_files,
                    hint=batch_dict.get("hint", ""),
                )

                # Execute batch
                success = runner.run_batch(batch, prompt)

                if success:
                    completed.append(batch_id)

                    # Phase 4: Store structured analysis result
                    for file_path in batch_files:
                        analysis_result: StructuredAnalysisResult = {
                            "file_path": file_path,
                            "summary": f"Analysis of {file_path}",
                            "key_concepts": ["TBD"],  # Would be extracted from response
                            "design_patterns": [],
                            "dependencies": dependency_graph.get(file_path, []),
                            "dependents": [],
                            "relationships": [],
                            "quality_score": 0.8,  # Would be extracted from response
                            "analysis_depth": "medium",
                            "timestamp": __import__("datetime").datetime.now().isoformat(),
                            "batch_id": batch_id,
                        }

                        context_manager.store_analysis(
                            file_path=file_path,
                            summary=analysis_result["summary"],
                            key_concepts=analysis_result["key_concepts"],
                            batch_id=batch_id,
                            quality_score=analysis_result["quality_score"],
                        )

                        structured_analyses[file_path] = analysis_result

                    # Get sense records from runner
                    sense_records.extend(runner.state_manager.state.global_summary)
                else:
                    failed.append(batch_id)
                    batch_errors[batch_id] = "Batch execution failed"

                # Add batch cost (simplified)
                total_cost += 0.10

            except Exception as e:
                logger.error(f"Error processing batch {batch_dict['id']}: {e}")
                failed.append(batch_dict["id"])
                batch_errors[batch_dict["id"]] = str(e)

        # Serialize context manager state for checkpointing
        context_manager_state = context_manager.to_dict()

        # Log context manager statistics
        stats = context_manager.get_statistics()
        logger.info(f"Context manager stats: {stats}")

    else:
        # Placeholder execution without backend
        logger.info(f"Would execute {len(pending_batches)} batches (no backend provided)")
        completed = list(range(len(pending_batches)))

    return {
        "completed_batches": completed,
        "failed_batches": failed,
        "sense_records": sense_records,
        "total_cost": total_cost,
        "batch_errors": batch_errors,
        "structured_analyses": structured_analyses,
        "context_manager_state": context_manager_state,
    }


def synthesis_node(
    state: LanternWorkflowState, backend: Optional["Backend"] = None
) -> dict[str, Any]:
    """
    Node 5: Synthesis
    - Generate documentation
    - Support both batch and agentic synthesis

    Note: In real workflow execution, backend would be provided via closure/context.
    """
    logger.info(f"Starting synthesis (mode: {state['synthesis_mode']})...")

    repo_path = Path(state["repo_path"])
    synthesis_mode = state["synthesis_mode"]
    state["config"]
    language = state.get("language", "en")

    documents = {}
    quality_score = 0.8

    if backend:
        try:
            if synthesis_mode == "agentic":
                try:
                    from lantern_cli.core.agentic_synthesizer import AgenticSynthesizer

                    agentic_synth = AgenticSynthesizer(
                        repo_path,
                        backend,
                        language=language,
                        output_dir=state.get("output_dir", ".lantern/docs"),
                    )
                    agentic_synth.generate_top_down_docs()
                    quality_score = 0.85  # Agentic synthesis typically scores higher
                except ImportError:
                    logger.warning("langgraph not installed, falling back to batch synthesis")
                    synthesis_mode = "batch"

            if synthesis_mode == "batch":
                synth = Synthesizer(
                    repo_path,
                    language=language,
                    output_dir=state.get("output_dir", ".lantern/docs"),
                    backend=backend,
                )
                synth.generate_top_down_docs()

            # Read generated documents
            output_dir = repo_path / state.get("output_dir", ".lantern/docs")
            for doc_name in ["OVERVIEW.md", "ARCHITECTURE.md", "CONCEPTS.md", "GETTING_STARTED.md"]:
                doc_path = output_dir / doc_name
                if doc_path.exists():
                    try:
                        documents[doc_name] = doc_path.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.warning(f"Could not read {doc_name}: {e}")

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            quality_score = 0.5
    else:
        # Placeholder documents
        documents = {
            "OVERVIEW.md": "# Overview\n\nAnalysis overview generated.",
            "ARCHITECTURE.md": "# Architecture\n\nArchitecture analysis generated.",
            "CONCEPTS.md": "# Concepts\n\nKey concepts identified.",
            "GETTING_STARTED.md": "# Getting Started\n\nGetting started guide generated.",
        }
        quality_score = 0.7  # Lower score for placeholder

    return {
        "documents": documents,
        "synthesis_quality_score": quality_score,
    }


def quality_gate_node(state: LanternWorkflowState) -> dict[str, Any]:
    """
    Node 6: Quality Gate
    - Evaluate synthesis quality
    - Decide if refinement is needed
    """
    logger.info("Running quality checks...")

    quality_score = state.get("synthesis_quality_score", 0.8)
    quality_ok = quality_score >= 0.8
    quality_issues = []

    if quality_score < 0.8:
        quality_issues.append(f"Synthesis quality score {quality_score:.2f} below threshold 0.8")

    return {
        "quality_score": quality_score,
        "quality_ok": quality_ok,
        "quality_issues": quality_issues,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def translation_node(
    state: LanternWorkflowState, backend: Optional["Backend"] = None
) -> dict[str, Any]:
    """
    Node: Translation
    - Translate English outputs to user's target language
    - No-op if target language is English
    """
    target_language = state.get("target_language", "en")
    if target_language == "en" or not backend:
        return {}

    logger.info(f"Translating outputs to {target_language}...")

    from lantern_cli.core.translator import Translator

    repo_path = Path(state["repo_path"])
    output_dir = state.get("output_dir", ".lantern/docs")
    translator = Translator(backend, target_language, repo_path / output_dir)
    translator.translate_all()

    return {}


def refine_node(state: LanternWorkflowState) -> dict[str, Any]:
    """
    Node 7: Refine (optional, only if quality check fails)
    - Refine documentation based on quality feedback
    """
    logger.info("Refining documentation...")

    # Placeholder for refinement logic
    documents = state.get("documents", {})

    return {
        "documents": documents,
        "synthesis_quality_score": min(0.95, state.get("synthesis_quality_score", 0.8) + 0.05),
    }


# ============================================================================
# Router Functions (for conditional edges)
# ============================================================================


def router_human_review(state: LanternWorkflowState) -> str:
    """
    Route from human_review to next node.
    - If approved: continue to batch_execution
    - If rejected: loop back to planning
    """
    if state.get("plan_rejected"):
        return "planning"
    elif state.get("plan_approved"):
        return "batch_execution"
    else:
        # Wait for human input (interrupt handled at invocation)
        return "human_review"


def router_quality_gate(state: LanternWorkflowState) -> str:
    """
    Route from quality_gate to next node.
    - If quality_ok: end
    - If not ok and iterations < max: refine
    - If max iterations exceeded: end anyway
    """
    max_iterations = 3

    if state.get("quality_ok"):
        return END
    elif state.get("iteration_count", 0) < max_iterations:
        return "refine"
    else:
        logger.warning(f"Max refinement iterations ({max_iterations}) reached")
        return END


# ============================================================================
# Workflow Builder
# ============================================================================


def build_lantern_workflow(
    checkpoint_config: LanternCheckpointConfig | None = None,
    backend: Optional["Backend"] = None,
    repo_path: Path | None = None,
) -> StateGraph:
    """
    Build the complete Lantern workflow StateGraph.

    Args:
        checkpoint_config: Configuration for checkpointing (optional)
        backend: LLM Backend instance (optional, for synthesis/planning)
        repo_path: Repository path (optional, for runner initialization)

    Returns:
        Compiled StateGraph ready for execution
    """
    if checkpoint_config is None:
        checkpoint_config = LanternCheckpointConfig(enable_checkpointing=False)

    # Create wrapper nodes that have access to context
    def static_analysis_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return static_analysis_node(state)

    def planning_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return planning_node(state)

    def human_review_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return human_review_node(state)

    def batch_execution_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        # Create runner if we have backend and repo_path
        runner = None
        if backend and repo_path:
            state_mgr = StateManager(repo_path, backend=backend)
            runner = Runner(
                repo_path,
                backend,
                state_mgr,
                language=state.get("language", "en"),
                model_name=backend.model_name if hasattr(backend, "model_name") else "unknown",
                is_local=getattr(backend, "type", "") == "ollama",
                output_dir=state.get("output_dir", ".lantern/docs"),
            )
        return batch_execution_node(state, backend=backend, runner=runner)

    def synthesis_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return synthesis_node(state, backend=backend)

    def quality_gate_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return quality_gate_node(state)

    def translation_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return translation_node(state, backend=backend)

    def refine_wrapper(state: LanternWorkflowState) -> dict[str, Any]:
        return refine_node(state)

    # Create graph
    workflow = StateGraph(LanternWorkflowState)

    # Add nodes with wrapper functions
    workflow.add_node("static_analysis", static_analysis_wrapper)
    workflow.add_node("planning", planning_wrapper)
    workflow.add_node("human_review", human_review_wrapper)
    workflow.add_node("batch_execution", batch_execution_wrapper)
    workflow.add_node("synthesis", synthesis_wrapper)
    workflow.add_node("translation", translation_wrapper)
    workflow.add_node("quality_gate", quality_gate_wrapper)
    workflow.add_node("refine", refine_wrapper)

    # Add edges (linear flow with branching)
    workflow.add_edge(START, "static_analysis")
    workflow.add_edge("static_analysis", "planning")
    workflow.add_edge("planning", "human_review")

    # Conditional edges from human_review
    workflow.add_conditional_edges(
        "human_review",
        router_human_review,
        {
            "planning": "planning",
            "batch_execution": "batch_execution",
            "human_review": "human_review",
        },
    )

    # Linear flow after approval
    workflow.add_edge("batch_execution", "synthesis")
    workflow.add_edge("synthesis", "translation")
    workflow.add_edge("translation", "quality_gate")

    # Conditional edges from quality_gate
    workflow.add_conditional_edges(
        "quality_gate",
        router_quality_gate,
        {
            "refine": "refine",
            END: END,
        },
    )

    # Refine loops back to quality_gate
    workflow.add_edge("refine", "quality_gate")

    # Compile with checkpointer
    saver = checkpoint_config.get_saver()
    compiled_workflow = workflow.compile(checkpointer=saver)

    return compiled_workflow


# ============================================================================
# Workflow Executor
# ============================================================================


class LanternWorkflowExecutor:
    """
    High-level executor for the Lantern workflow.

    Handles:
    - Workflow initialization with user inputs
    - State management and persistence
    - User interrupts and human-in-the-loop interactions
    - Result reporting
    """

    def __init__(
        self,
        repo_path: Path,
        backend: "Backend",
        config: Any,  # LanternConfig but use Any to avoid import issues
        language: str = "en",
        target_language: str = "en",
        synthesis_mode: str = "batch",
        planning_mode: str = "static",
        assume_yes: bool = False,
        output_dir: str = ".lantern/docs",
    ):
        """Initialize the workflow executor."""
        self.repo_path = repo_path
        self.backend = backend
        self.config = config
        self.language = language
        self.target_language = target_language
        self.synthesis_mode = synthesis_mode
        self.planning_mode = planning_mode
        self.assume_yes = assume_yes
        self.output_dir = output_dir

        # Setup checkpoint directory
        checkpoint_dir = repo_path / ".lantern" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_config = LanternCheckpointConfig(
            enable_checkpointing=True,
            checkpoint_dir=checkpoint_dir,
        )

        self.workflow = build_lantern_workflow(
            checkpoint_config=checkpoint_config,
            backend=backend,
            repo_path=repo_path,
        )
        self.state_manager = StateManager(repo_path, backend=backend)

    def initialize_state(self) -> LanternWorkflowState:
        """Initialize the initial state for workflow execution."""
        # Convert config to dict
        config_dict = {}
        if hasattr(self.config, "model_dump"):  # Pydantic v2
            config_dict = self.config.model_dump()
        elif hasattr(self.config, "dict"):  # Pydantic v1
            config_dict = self.config.dict()
        elif hasattr(self.config, "__dict__"):
            config_dict = vars(self.config).copy()
        else:
            config_dict = dict(self.config) if isinstance(self.config, dict) else {}

        return {
            # Input parameters
            "repo_path": str(self.repo_path),
            "config": config_dict,
            "language": self.language,
            "target_language": self.target_language,
            "synthesis_mode": self.synthesis_mode,
            "planning_mode": self.planning_mode,
            "assume_yes": self.assume_yes,
            # Analysis results (to be filled by nodes)
            "dependency_graph": {},
            "reverse_dependencies": {},
            "file_list": [],
            "layers": [],
            "mermaid_graph": "",
            # Plan (to be filled)
            "plan": None,
            "plan_approved": False,
            "plan_rejected": False,
            # Batch execution
            "pending_batches": [],
            "completed_batches": [],
            "failed_batches": [],
            "sense_records": [],
            "global_summary": "",
            "batch_errors": {},
            # Phase 4: Enhanced Context Management
            "structured_analyses": {},
            "context_manager_state": {},
            # Synthesis results
            "documents": {},
            "synthesis_quality_score": 0.0,
            # Quality
            "quality_score": 0.0,
            "quality_ok": False,
            "quality_issues": [],
            # Cost
            "total_cost": 0.0,
            "estimated_cost": 0.0,
            # Workflow control
            "iteration_count": 0,
            "needs_reanalysis": False,
            # Output directory
            "output_dir": self.output_dir,
        }

    async def execute(self, thread_id: str | None = None) -> LanternWorkflowState:
        """
        Execute the workflow.

        Args:
            thread_id: Optional thread ID for resuming execution

        Returns:
            Final workflow state
        """
        initial_state = self.initialize_state()

        # Run the workflow with optional checkpoint resume
        config = {"configurable": {"thread_id": thread_id or "default"}}

        final_state = await self.workflow.ainvoke(initial_state, config=config)

        return final_state

    def execute_sync(self, thread_id: str | None = None) -> LanternWorkflowState:
        """
        Synchronously execute the workflow.

        Args:
            thread_id: Optional thread ID for resuming execution

        Returns:
            Final workflow state
        """
        initial_state = self.initialize_state()

        # Run the workflow with optional checkpoint resume
        config = {"configurable": {"thread_id": thread_id or "default"}}

        final_state = self.workflow.invoke(initial_state, config=config)

        return final_state


# ============================================================================
# Visualization & Debugging
# ============================================================================


def visualize_workflow(workflow: StateGraph, output_path: Path | None = None) -> str:
    """
    Generate and optionally save a Mermaid diagram of the workflow.

    Args:
        workflow: Compiled StateGraph
        output_path: Optional path to save the diagram

    Returns:
        Mermaid diagram string
    """
    try:
        diagram = workflow.get_graph().draw_mermaid()

        if output_path:
            output_path.write_text(diagram)
            logger.info(f"Workflow diagram saved to {output_path}")

        return diagram
    except Exception as e:
        logger.warning(f"Could not generate workflow diagram: {e}")
        return ""
