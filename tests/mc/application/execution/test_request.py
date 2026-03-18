"""Tests for ExecutionRequest, ExecutionResult, and supporting types."""

from __future__ import annotations

from pathlib import Path

from mc.application.execution.request import (
    EntityType,
    ErrorCategory,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)

# ---------------------------------------------------------------------------
# Story 16.1 — EntityType
# ---------------------------------------------------------------------------


class TestEntityType:
    """Tests for EntityType constants."""

    def test_task_constant(self) -> None:
        assert EntityType.TASK == "task"

    def test_step_constant(self) -> None:
        assert EntityType.STEP == "step"


# ---------------------------------------------------------------------------
# Story 16.2 — RunnerType and ErrorCategory
# ---------------------------------------------------------------------------


class TestRunnerType:
    def test_nanobot_value(self) -> None:
        assert RunnerType.NANOBOT.value == "nanobot"

    def test_claude_code_value(self) -> None:
        assert RunnerType.CLAUDE_CODE.value == "claude-code"

    def test_human_value(self) -> None:
        assert RunnerType.HUMAN.value == "human"

    def test_interactive_tui_value(self) -> None:
        assert RunnerType.INTERACTIVE_TUI.value == "interactive-tui"


class TestErrorCategory:
    def test_all_categories(self) -> None:
        assert ErrorCategory.TIER.value == "tier"
        assert ErrorCategory.PROVIDER.value == "provider"
        assert ErrorCategory.RUNNER.value == "runner"
        assert ErrorCategory.WORKFLOW.value == "workflow"


# ---------------------------------------------------------------------------
# Story 16.1 — ExecutionRequest defaults and fields
# ---------------------------------------------------------------------------


class TestExecutionRequestDefaults:
    """Tests for ExecutionRequest default values."""

    def test_minimal_task_request(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_123",
            task_id="task_123",
        )
        assert req.entity_type == "task"
        assert req.entity_id == "task_123"
        assert req.task_id == "task_123"
        assert req.title == ""
        assert req.description is None
        assert req.agent is None
        assert req.agent_name == ""
        assert req.files == []
        assert req.file_manifest == []
        assert req.thread_context == ""
        assert req.predecessor_context == ""
        assert req.predecessor_step_ids == []
        assert req.tags == []
        assert req.tag_attributes == ""
        assert req.trust_level == "autonomous"
        assert req.is_cc is False
        assert req.task_data == {}
        # 16.2 defaults
        assert req.runner_type == RunnerType.NANOBOT
        assert req.step_id is None
        assert req.session_key is None

    def test_minimal_step_request(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id="step_456",
            task_id="task_123",
        )
        assert req.entity_type == "step"
        assert req.entity_id == "step_456"
        assert req.task_id == "task_123"

    def test_is_task_property(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
        )
        assert req.is_task is True
        assert req.is_step is False

    def test_is_step_property(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id="s1",
            task_id="t1",
        )
        assert req.is_task is False
        assert req.is_step is True


class TestExecutionRequestPopulated:
    """Tests for ExecutionRequest with populated fields."""

    def test_full_task_request(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_abc",
            task_id="task_abc",
            title="Test Task",
            description="A test task",
            agent_name="test-agent",
            agent_prompt="You are a test agent",
            agent_model="gpt-4",
            agent_skills=["code", "write"],
            board_name="dev-board",
            memory_workspace=Path("/tmp/memory"),
            files=[{"name": "doc.pdf"}],
            file_manifest=[{"name": "doc.pdf", "type": "application/pdf"}],
            files_dir="/tasks/abc",
            output_dir="/tasks/abc/output",
            thread_context="[Thread History]\nUser: hello",
            tags=["urgent"],
            tag_attributes="urgent: priority=high",
            trust_level="human_approved",
            task_data={"id": "task_abc", "title": "Test Task"},
            runner_type=RunnerType.CLAUDE_CODE,
            session_key="mc:task:test-agent:task_abc",
        )
        assert req.title == "Test Task"
        assert req.agent_name == "test-agent"
        assert req.board_name == "dev-board"
        assert req.memory_workspace == Path("/tmp/memory")
        assert len(req.files) == 1
        assert len(req.file_manifest) == 1
        assert req.thread_context.startswith("[Thread History]")
        assert req.tags == ["urgent"]
        assert req.trust_level == "human_approved"
        assert req.runner_type == RunnerType.CLAUDE_CODE
        assert req.session_key == "mc:task:test-agent:task_abc"

    def test_step_request_with_predecessors(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.STEP,
            entity_id="step_1",
            task_id="task_abc",
            step_title="Implement feature",
            step_description="Implement the feature",
            predecessor_step_ids=["step_0"],
            predecessor_context="[Predecessor Context]\nstep_0 completed",
            blocked_by=["step_0"],
            step_id="step_1",
        )
        assert req.step_title == "Implement feature"
        assert req.predecessor_step_ids == ["step_0"]
        assert req.blocked_by == ["step_0"]
        assert "Predecessor" in req.predecessor_context
        assert req.step_id == "step_1"

    def test_cc_request(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_cc",
            task_id="task_cc",
            is_cc=True,
            model="claude-sonnet-4-20250514",
        )
        assert req.is_cc is True
        assert req.model == "claude-sonnet-4-20250514"

    def test_human_runner_type(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_human",
            task_id="task_human",
            runner_type=RunnerType.HUMAN,
        )
        assert req.runner_type == RunnerType.HUMAN


class TestExecutionRequestSafeTaskId:
    """Tests for safe_task_id property."""

    def test_safe_task_id_strips_prefix(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_abc",
            task_id="task_abc",
        )
        safe_id = req.safe_task_id
        assert isinstance(safe_id, str)
        assert len(safe_id) > 0


class TestExecutionRequestMutability:
    """Tests that ExecutionRequest fields can be mutated during pipeline stages."""

    def test_can_set_prompt_after_creation(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
        )
        req.prompt = "assembled prompt"
        assert req.prompt == "assembled prompt"

    def test_can_set_agent_after_creation(self) -> None:
        from mc.types import AgentData

        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
        )
        req.agent = AgentData(
            name="test",
            display_name="Test",
            role="agent",
        )
        assert req.agent is not None
        assert req.agent.name == "test"

    def test_lists_are_independent_between_instances(self) -> None:
        req1 = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t1",
            task_id="t1",
        )
        req2 = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="t2",
            task_id="t2",
        )
        req1.files.append({"name": "a.txt"})
        assert len(req2.files) == 0


# ---------------------------------------------------------------------------
# Story 16.2 — ExecutionResult
# ---------------------------------------------------------------------------


class TestExecutionResult:
    def test_success_result(self) -> None:
        result = ExecutionResult(success=True, output="Done!")
        assert result.success is True
        assert result.output == "Done!"
        assert result.error_category is None
        assert result.error_message is None
        assert result.cost_usd == 0.0
        assert result.session_id is None
        assert result.artifacts == []
        assert result.transition_status is None

    def test_error_result(self) -> None:
        result = ExecutionResult(
            success=False,
            error_category=ErrorCategory.PROVIDER,
            error_message="OAuth expired",
        )
        assert result.success is False
        assert result.error_category == ErrorCategory.PROVIDER
        assert result.error_message == "OAuth expired"

    def test_result_with_metadata(self) -> None:
        result = ExecutionResult(
            success=True,
            output="All done",
            cost_usd=0.0534,
            session_id="sess_abc123",
            artifacts=[{"path": "output/report.pdf", "action": "created"}],
        )
        assert result.cost_usd == 0.0534
        assert result.session_id == "sess_abc123"
        assert len(result.artifacts) == 1

    def test_transition_status(self) -> None:
        result = ExecutionResult(
            success=True,
            output="Waiting for human.",
            transition_status="waiting_human",
        )
        assert result.transition_status == "waiting_human"
