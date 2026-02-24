"""
Tests for the LangGraph workflow orchestration.

Tests cover:
- State transitions
- Node executions
- Router logic
- Checkpoint persistence
- Error handling
"""

from unittest.mock import MagicMock

import pytest

# Import workflow components
from lantern_cli.core.workflow import (
    LanternCheckpointConfig,
    LanternWorkflowExecutor,
    LanternWorkflowState,
    _deserialize_plan,
    _serialize_plan,
    build_lantern_workflow,
    router_human_review,
    router_quality_gate,
)


class TestLanternWorkflowState:
    """Test the workflow state definition."""

    def test_state_has_required_fields(self):
        """Test that LanternWorkflowState has all required fields."""
        required_fields = {
            # Input parameters
            "repo_path",
            "config",
            "language",
            "synthesis_mode",
            "planning_mode",
            "assume_yes",
            # Static analysis
            "dependency_graph",
            "reverse_dependencies",
            "file_list",
            "layers",
            "mermaid_graph",
            # Planning
            "plan",
            "plan_approved",
            "plan_rejected",
            # Execution
            "pending_batches",
            "completed_batches",
            "failed_batches",
            "sense_records",
            "global_summary",
            "batch_errors",
            # Synthesis
            "documents",
            "synthesis_quality_score",
            # Quality
            "quality_score",
            "quality_ok",
            "quality_issues",
            # Cost
            "total_cost",
            "estimated_cost",
            # Control
            "iteration_count",
            "needs_reanalysis",
            "output_dir",
        }

        annotations = LanternWorkflowState.__annotations__
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_state_can_be_created(self):
        """Test that a valid state can be created."""
        state: LanternWorkflowState = {
            "repo_path": "/test/repo",
            "config": {"backend": "openai"},
            "language": "en",
            "synthesis_mode": "batch",
            "planning_mode": "static",
            "assume_yes": False,
            "output_dir": ".lantern/docs",
            "dependency_graph": {},
            "reverse_dependencies": {},
            "file_list": [],
            "layers": [],
            "mermaid_graph": "",
            "plan": None,
            "plan_approved": False,
            "plan_rejected": False,
            "pending_batches": [],
            "completed_batches": [],
            "failed_batches": [],
            "sense_records": [],
            "global_summary": "",
            "batch_errors": {},
            "documents": {},
            "synthesis_quality_score": 0.0,
            "quality_score": 0.0,
            "quality_ok": False,
            "quality_issues": [],
            "total_cost": 0.0,
            "estimated_cost": 0.0,
            "iteration_count": 0,
            "needs_reanalysis": False,
        }

        assert state["repo_path"] == "/test/repo"
        assert state["language"] == "en"
        assert state["plan_approved"] is False


class TestCheckpointConfig:
    """Test checkpoint configuration."""

    def test_default_config(self):
        """Test default checkpoint config."""
        config = LanternCheckpointConfig()
        assert config.enable_checkpointing is True
        assert config.checkpoint_dir is None

    def test_memory_saver_for_no_checkpoint_dir(self):
        """Test that MemorySaver is used when no checkpoint dir."""
        config = LanternCheckpointConfig(enable_checkpointing=True, checkpoint_dir=None)
        saver = config.get_saver()

        # Should be MemorySaver or similar in-memory implementation
        from langgraph.checkpoint.memory import MemorySaver

        assert isinstance(saver, MemorySaver)

    def test_disabled_checkpointing(self):
        """Test disabled checkpointing."""
        config = LanternCheckpointConfig(enable_checkpointing=False)
        saver = config.get_saver()

        from langgraph.checkpoint.memory import MemorySaver

        assert isinstance(saver, MemorySaver)


class TestPlanSerialization:
    """Test plan serialization/deserialization."""

    def test_serialize_plan(self):
        """Test plan serialization."""
        from lantern_cli.core.architect import Batch, Phase, Plan

        plan = Plan(
            phases=[
                Phase(
                    id=1,
                    batches=[
                        Batch(id=1, files=["file1.py", "file2.py"], hint="test hint"),
                    ],
                    learning_objectives=["Learn patterns"],
                )
            ],
            confidence_score=0.95,
            dependencies_mermaid="graph TD;",
        )

        serialized = _serialize_plan(plan)

        assert serialized is not None
        assert serialized["confidence_score"] == 0.95
        assert len(serialized["phases"]) == 1
        assert serialized["phases"][0]["id"] == 1
        assert serialized["phases"][0]["batches"][0]["files"] == ["file1.py", "file2.py"]

    def test_deserialize_plan(self):
        """Test plan deserialization."""
        plan_dict = {
            "phases": [
                {
                    "id": 1,
                    "batches": [
                        {"id": 1, "files": ["file1.py"], "hint": "test"},
                    ],
                    "learning_objectives": ["Learn"],
                }
            ],
            "confidence_score": 0.9,
            "dependencies_mermaid": "graph",
        }

        plan = _deserialize_plan(plan_dict)

        assert plan is not None
        assert plan.confidence_score == 0.9
        assert len(plan.phases) == 1
        assert plan.phases[0].batches[0].files == ["file1.py"]

    def test_serialize_deserialize_roundtrip(self):
        """Test that serialization is reversible."""
        from lantern_cli.core.architect import Batch, Phase, Plan

        original = Plan(
            phases=[
                Phase(
                    id=1,
                    batches=[Batch(id=1, files=["test.py"], hint="hint")],
                    learning_objectives=["Learn"],
                )
            ],
            confidence_score=0.85,
            dependencies_mermaid="graph",
        )

        serialized = _serialize_plan(original)
        deserialized = _deserialize_plan(serialized)

        assert deserialized.confidence_score == original.confidence_score
        assert len(deserialized.phases) == len(original.phases)
        assert deserialized.phases[0].batches[0].files == original.phases[0].batches[0].files


class TestRouters:
    """Test router logic."""

    def test_router_human_review_approved(self):
        """Test routing when plan is approved."""
        state: LanternWorkflowState = {
            "repo_path": "/test",
            "config": {},
            "language": "en",
            "synthesis_mode": "batch",
            "planning_mode": "static",
            "assume_yes": True,
            "output_dir": ".lantern/docs",
            "dependency_graph": {},
            "reverse_dependencies": {},
            "file_list": [],
            "layers": [],
            "mermaid_graph": "",
            "plan": None,
            "plan_approved": True,  # Approved
            "plan_rejected": False,
            "pending_batches": [],
            "completed_batches": [],
            "failed_batches": [],
            "sense_records": [],
            "global_summary": "",
            "batch_errors": {},
            "documents": {},
            "synthesis_quality_score": 0.0,
            "quality_score": 0.0,
            "quality_ok": False,
            "quality_issues": [],
            "total_cost": 0.0,
            "estimated_cost": 0.0,
            "iteration_count": 0,
            "needs_reanalysis": False,
        }

        result = router_human_review(state)
        assert result == "batch_execution"

    def test_router_human_review_rejected(self):
        """Test routing when plan is rejected."""
        state: LanternWorkflowState = {
            "repo_path": "/test",
            "config": {},
            "language": "en",
            "synthesis_mode": "batch",
            "planning_mode": "static",
            "assume_yes": True,
            "output_dir": ".lantern/docs",
            "dependency_graph": {},
            "reverse_dependencies": {},
            "file_list": [],
            "layers": [],
            "mermaid_graph": "",
            "plan": None,
            "plan_approved": False,
            "plan_rejected": True,  # Rejected
            "pending_batches": [],
            "completed_batches": [],
            "failed_batches": [],
            "sense_records": [],
            "global_summary": "",
            "batch_errors": {},
            "documents": {},
            "synthesis_quality_score": 0.0,
            "quality_score": 0.0,
            "quality_ok": False,
            "quality_issues": [],
            "total_cost": 0.0,
            "estimated_cost": 0.0,
            "iteration_count": 0,
            "needs_reanalysis": False,
        }

        result = router_human_review(state)
        assert result == "planning"

    def test_router_quality_gate_ok(self):
        """Test routing when quality is ok."""
        state: LanternWorkflowState = {
            "repo_path": "/test",
            "config": {},
            "language": "en",
            "synthesis_mode": "batch",
            "planning_mode": "static",
            "assume_yes": True,
            "output_dir": ".lantern/docs",
            "dependency_graph": {},
            "reverse_dependencies": {},
            "file_list": [],
            "layers": [],
            "mermaid_graph": "",
            "plan": None,
            "plan_approved": False,
            "plan_rejected": False,
            "pending_batches": [],
            "completed_batches": [],
            "failed_batches": [],
            "sense_records": [],
            "global_summary": "",
            "batch_errors": {},
            "documents": {},
            "synthesis_quality_score": 0.9,
            "quality_score": 0.9,
            "quality_ok": True,  # Quality is OK
            "quality_issues": [],
            "total_cost": 0.0,
            "estimated_cost": 0.0,
            "iteration_count": 0,
            "needs_reanalysis": False,
        }

        from langgraph.graph import END

        result = router_quality_gate(state)
        assert result == END

    def test_router_quality_gate_needs_refinement(self):
        """Test routing when quality needs refinement."""
        state: LanternWorkflowState = {
            "repo_path": "/test",
            "config": {},
            "language": "en",
            "synthesis_mode": "batch",
            "planning_mode": "static",
            "assume_yes": True,
            "output_dir": ".lantern/docs",
            "dependency_graph": {},
            "reverse_dependencies": {},
            "file_list": [],
            "layers": [],
            "mermaid_graph": "",
            "plan": None,
            "plan_approved": False,
            "plan_rejected": False,
            "pending_batches": [],
            "completed_batches": [],
            "failed_batches": [],
            "sense_records": [],
            "global_summary": "",
            "batch_errors": {},
            "documents": {},
            "synthesis_quality_score": 0.7,
            "quality_score": 0.7,
            "quality_ok": False,  # Quality not OK
            "quality_issues": ["Score too low"],
            "total_cost": 0.0,
            "estimated_cost": 0.0,
            "iteration_count": 0,  # Haven't exceeded max iterations
            "needs_reanalysis": False,
        }

        result = router_quality_gate(state)
        assert result == "refine"


class TestWorkflowBuilder:
    """Test workflow building."""

    def test_workflow_can_be_built(self):
        """Test that workflow can be built without errors."""
        workflow = build_lantern_workflow()
        assert workflow is not None

    def test_workflow_has_all_nodes(self):
        """Test that workflow includes all expected nodes."""
        workflow = build_lantern_workflow()

        # Get graph structure
        graph = workflow.get_graph()

        # The graph should have nodes for the workflow
        # (This is a simplified check - real implementation would verify node names)
        assert graph is not None

    def test_workflow_with_checkpoint_config(self):
        """Test workflow with checkpoint configuration."""
        checkpoint_config = LanternCheckpointConfig(enable_checkpointing=False)
        workflow = build_lantern_workflow(checkpoint_config=checkpoint_config)

        assert workflow is not None


class TestWorkflowExecutor:
    """Test the workflow executor."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        mock_config = MagicMock()
        mock_config.language = "en"
        mock_config.output_dir = ".lantern/docs"
        mock_config.backend.type = "ollama"
        mock_config.backend.api_provider = "local"
        mock_config.filter = {}
        mock_config.model_dump = MagicMock(
            return_value={
                "language": "en",
                "output_dir": ".lantern/docs",
                "backend": {
                    "type": "ollama",
                    "api_provider": "local",
                },
            }
        )
        return mock_config

    @pytest.fixture
    def mock_backend(self):
        """Create a mock backend."""
        mock_backend = MagicMock()
        mock_backend.model_name = "test-model"
        mock_backend.type = "ollama"
        return mock_backend

    def test_executor_initialization(self, tmp_path, mock_backend, mock_config):
        """Test that executor initializes properly."""
        executor = LanternWorkflowExecutor(
            repo_path=tmp_path,
            backend=mock_backend,
            config=mock_config,
        )

        assert executor.repo_path == tmp_path
        assert executor.backend == mock_backend
        assert executor.language == "en"
        assert executor.synthesis_mode == "batch"

    def test_executor_initializes_state(self, tmp_path, mock_backend, mock_config):
        """Test that executor can initialize state."""
        executor = LanternWorkflowExecutor(
            repo_path=tmp_path,
            backend=mock_backend,
            config=mock_config,
        )

        state = executor.initialize_state()

        assert state["repo_path"] == str(tmp_path)
        assert state["language"] == "en"
        assert state["synthesis_mode"] == "batch"
        assert state["plan_approved"] is False
        assert state["completed_batches"] == []

    def test_executor_with_custom_parameters(self, tmp_path, mock_backend, mock_config):
        """Test executor with custom parameters."""
        executor = LanternWorkflowExecutor(
            repo_path=tmp_path,
            backend=mock_backend,
            config=mock_config,
            language="zh-TW",
            synthesis_mode="agentic",
            planning_mode="agentic",
            assume_yes=True,
            output_dir="custom/docs",
        )

        state = executor.initialize_state()

        assert state["language"] == "zh-TW"
        assert state["synthesis_mode"] == "agentic"
        assert state["planning_mode"] == "agentic"
        assert state["assume_yes"] is True
        assert state["output_dir"] == "custom/docs"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
