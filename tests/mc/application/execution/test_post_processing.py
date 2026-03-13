"""Tests for canonical post-execution memory hooks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mc.application.execution.post_processing import (
    build_cc_task_memory_consolidation_hook,
)
from mc.application.execution.request import (
    EntityType,
    ExecutionRequest,
    ExecutionResult,
    RunnerType,
)


def _cc_request(*, boundary_reason: str | None) -> ExecutionRequest:
    return ExecutionRequest(
        entity_type=EntityType.TASK,
        entity_id="task-1",
        task_id="task-1",
        title="Consolidate this task",
        agent_name="cc-agent",
        runner_type=RunnerType.CLAUDE_CODE,
        session_boundary_reason=boundary_reason,
    )


def _cc_result(tmp_path: Path) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        output="task output",
        session_id="sess-cc-1",
        memory_workspace=tmp_path,
    )


class TestCCTaskMemoryConsolidationHook:
    """Claude Code task consolidation should use the canonical hook path."""

    @pytest.mark.asyncio
    async def test_task_boundary_schedules_cc_consolidation(self, tmp_path: Path) -> None:
        hook = build_cc_task_memory_consolidation_hook(bridge=MagicMock())
        request = _cc_request(boundary_reason="task_completion")
        result = _cc_result(tmp_path)
        scheduled: list[asyncio.Task[None]] = []

        def _run_now(coro):
            task = asyncio.create_task(coro)
            scheduled.append(task)
            return task

        with (
            patch(
                "mc.application.execution.post_processing.create_background_task",
                side_effect=_run_now,
            ),
            patch(
                "mc.application.execution.post_processing.resolve_consolidation_model",
                return_value="claude-test-model",
            ),
            patch(
                "mc.application.execution.post_processing.consolidate_task_output",
                new=AsyncMock(return_value=True),
            ) as consolidate_mock,
        ):
            await hook(request, result)
            await asyncio.gather(*scheduled)

        consolidate_mock.assert_awaited_once_with(
            tmp_path,
            task_title="Consolidate this task",
            task_output="task output",
            task_status="completed",
            task_id="task-1",
            model="claude-test-model",
        )

    @pytest.mark.asyncio
    async def test_non_boundary_chat_request_skips_cc_consolidation(self, tmp_path: Path) -> None:
        hook = build_cc_task_memory_consolidation_hook(bridge=MagicMock())
        request = _cc_request(boundary_reason=None)
        result = _cc_result(tmp_path)

        with (
            patch(
                "mc.application.execution.post_processing.create_background_task"
            ) as create_task_mock,
            patch(
                "mc.application.execution.post_processing.consolidate_task_output",
                new=AsyncMock(return_value=True),
            ) as consolidate_mock,
        ):
            await hook(request, result)

        create_task_mock.assert_not_called()
        consolidate_mock.assert_not_awaited()
