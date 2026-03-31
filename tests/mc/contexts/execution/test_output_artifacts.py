"""Tests for execution output artifact helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mc.contexts.execution.output_artifacts import write_prompt_log


class TestWritePromptLog:
    """Tests for prompt log persistence."""

    def test_writes_prompt_log_to_internal_logs_dir(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"

        with patch(
            "mc.contexts.execution.output_artifacts.get_tasks_dir",
            return_value=tasks_dir,
        ):
            write_prompt_log(
                "task_123",
                "system_prompt_log_{DDHHMMSS}.txt",
                "assembled prompt",
                step_id="step_abcdef",
            )

        log_dir = tasks_dir / "task_123" / "output" / ".internal" / "logs"
        files = list(log_dir.iterdir())

        assert len(files) == 1
        assert files[0].name.startswith("system_prompt_log_")
        assert files[0].name.endswith("_abcdef.txt")
        assert files[0].read_text(encoding="utf-8") == "assembled prompt"
