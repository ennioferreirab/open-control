"""Tests for ExecutionResult data model."""

from __future__ import annotations

from mc.application.execution.result import ExecutionResult


class TestExecutionResultDefaults:
    """Tests for ExecutionResult default values."""

    def test_minimal_result(self) -> None:
        result = ExecutionResult()
        assert result.output == ""
        assert result.is_error is False
        assert result.artifacts == []
        assert result.session_key is None
        assert result.session_id is None
        assert result.cost_usd == 0.0
        assert result.entity_type == "task"

    def test_has_artifacts_empty(self) -> None:
        result = ExecutionResult()
        assert result.has_artifacts is False

    def test_has_artifacts_present(self) -> None:
        result = ExecutionResult(
            artifacts=[{"path": "output/report.pdf", "action": "created"}]
        )
        assert result.has_artifacts is True


class TestExecutionResultPopulated:
    """Tests for ExecutionResult with populated fields."""

    def test_successful_task_result(self) -> None:
        result = ExecutionResult(
            output="Task completed successfully",
            is_error=False,
            artifacts=[
                {"path": "output/report.pdf", "action": "created"},
                {"path": "output/data.json", "action": "modified"},
            ],
            session_key="mc:task:agent:t1",
            entity_type="task",
        )
        assert result.output == "Task completed successfully"
        assert result.is_error is False
        assert len(result.artifacts) == 2
        assert result.session_key == "mc:task:agent:t1"

    def test_error_result(self) -> None:
        result = ExecutionResult(
            output="RuntimeError: something went wrong",
            is_error=True,
            entity_type="step",
        )
        assert result.is_error is True
        assert result.entity_type == "step"

    def test_cc_result(self) -> None:
        result = ExecutionResult(
            output="CC output",
            session_id="cc_session_123",
            cost_usd=0.0234,
        )
        assert result.session_id == "cc_session_123"
        assert result.cost_usd == 0.0234


class TestExecutionResultListIndependence:
    """Tests that list fields are independent between instances."""

    def test_artifacts_independent(self) -> None:
        r1 = ExecutionResult()
        r2 = ExecutionResult()
        r1.artifacts.append({"path": "a.txt", "action": "created"})
        assert len(r2.artifacts) == 0
