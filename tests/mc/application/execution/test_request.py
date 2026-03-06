"""Tests for ExecutionRequest data model."""

from __future__ import annotations

from pathlib import Path

from mc.application.execution.request import EntityType, ExecutionRequest


class TestEntityType:
    """Tests for EntityType constants."""

    def test_task_constant(self) -> None:
        assert EntityType.TASK == "task"

    def test_step_constant(self) -> None:
        assert EntityType.STEP == "step"


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
        )
        assert req.step_title == "Implement feature"
        assert req.predecessor_step_ids == ["step_0"]
        assert req.blocked_by == ["step_0"]
        assert "Predecessor" in req.predecessor_context

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


class TestExecutionRequestSafeTaskId:
    """Tests for safe_task_id property."""

    def test_safe_task_id_strips_prefix(self) -> None:
        req = ExecutionRequest(
            entity_type=EntityType.TASK,
            entity_id="task_abc",
            task_id="task_abc",
        )
        # task_safe_id should work on any string
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
