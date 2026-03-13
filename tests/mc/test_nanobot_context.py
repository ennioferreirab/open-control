from __future__ import annotations

from pathlib import Path

from nanobot.agent.context import ContextBuilder


def test_system_prompt_mentions_board_artifacts_when_available(tmp_path: Path) -> None:
    workspace = tmp_path / "agent"
    (workspace / "memory").mkdir(parents=True)
    artifacts_dir = tmp_path / "boards" / "default" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    builder = ContextBuilder(workspace, artifacts_workspace=artifacts_dir)

    prompt = builder.build_system_prompt()

    assert f"Board artifacts: {artifacts_dir}" in prompt
    assert "Task-specific deliverables belong in task output directories" in prompt
