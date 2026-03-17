"""Tests for skills sync — Story 8.2, Task 1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_workspace(tmp_path, monkeypatch):
    """Prevent sync_skills from picking up real workspace skills."""
    empty_ws = tmp_path / "empty_workspace"
    empty_ws.mkdir()
    fake_config = MagicMock()
    fake_config.workspace_path = empty_ws
    monkeypatch.setattr("nanobot.config.loader.load_config", lambda: fake_config)


def _make_skill_md(
    name: str,
    description: str,
    *,
    always: bool = False,
    metadata: Optional[dict] = None,
    body: str = "# Skill content",
) -> str:
    """Build a SKILL.md string with frontmatter."""
    lines = ["---"]
    lines.append(f"name: {name}")
    lines.append(f'description: "{description}"')
    if always:
        lines.append("always: true")
    if metadata:
        lines.append(f"metadata: {json.dumps(metadata)}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _create_skill_dir(base_dir: Path, name: str, content: str) -> Path:
    """Create a skill directory with SKILL.md."""
    skill_dir = base_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


class TestSyncSkills:
    """Test sync_skills() discovers skills and syncs them to Convex."""

    def test_discovers_builtin_skills_and_calls_upsert(self, tmp_path):
        """sync_skills should find SKILL.md files and call upsert for each."""
        from mc.runtime.gateway import sync_skills

        skills_dir = tmp_path / "skills"
        _create_skill_dir(
            skills_dir,
            "github",
            _make_skill_md(
                "github",
                "GitHub CLI integration",
                metadata={"nanobot": {"emoji": "\U0001f419", "requires": {"bins": ["gh"]}}},
            ),
        )
        _create_skill_dir(
            skills_dir,
            "memory",
            _make_skill_md(
                "memory",
                "Two-layer memory system",
                always=True,
            ),
        )

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        # Should have called mutation for each skill + deactivateExcept
        upsert_calls = [
            c for c in mock_bridge.mutation.call_args_list if c[0][0] == "skills:upsertByName"
        ]
        assert len(upsert_calls) == 2

        # Check skill names synced
        synced_names = {c[0][1]["name"] for c in upsert_calls}
        assert synced_names == {"github", "memory"}

    def test_strips_frontmatter_from_content(self, tmp_path):
        """Content field should be the body without frontmatter."""
        from mc.runtime.gateway import sync_skills

        body = "# GitHub Skill\n\nUse `gh` CLI."
        skills_dir = tmp_path / "skills"
        _create_skill_dir(
            skills_dir,
            "github",
            _make_skill_md(
                "github",
                "GitHub CLI",
                body=body,
            ),
        )

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        upsert_call = mock_bridge.mutation.call_args_list[0]
        args = upsert_call[0][1]
        assert args["content"] == body
        assert "---" not in args["content"]

    def test_sets_always_field(self, tmp_path):
        """Skills with always: true in frontmatter should have always=True."""
        from mc.runtime.gateway import sync_skills

        skills_dir = tmp_path / "skills"
        _create_skill_dir(
            skills_dir,
            "memory",
            _make_skill_md(
                "memory",
                "Memory system",
                always=True,
            ),
        )

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        upsert_call = mock_bridge.mutation.call_args_list[0]
        args = upsert_call[0][1]
        assert args["always"] is True

    def test_sets_source_builtin(self, tmp_path):
        """Skills from builtin dir should have source='builtin'."""
        from mc.runtime.gateway import sync_skills

        skills_dir = tmp_path / "skills"
        _create_skill_dir(
            skills_dir,
            "weather",
            _make_skill_md(
                "weather",
                "Weather data",
            ),
        )

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        upsert_call = mock_bridge.mutation.call_args_list[0]
        args = upsert_call[0][1]
        assert args["source"] == "builtin"

    def test_calls_deactivate_except(self, tmp_path):
        """Should call deactivateExcept with active skill names."""
        from mc.runtime.gateway import sync_skills

        skills_dir = tmp_path / "skills"
        _create_skill_dir(skills_dir, "github", _make_skill_md("github", "GitHub"))
        _create_skill_dir(skills_dir, "weather", _make_skill_md("weather", "Weather"))

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        deactivate_calls = [
            c for c in mock_bridge.mutation.call_args_list if c[0][0] == "skills:deactivateExcept"
        ]
        assert len(deactivate_calls) == 1
        active_names = set(deactivate_calls[0][0][1]["active_names"])
        assert active_names == {"github", "weather"}

    def test_checks_requirements_availability(self, tmp_path):
        """Skills with unmet requirements should have available=False."""
        from mc.runtime.gateway import sync_skills

        skills_dir = tmp_path / "skills"
        _create_skill_dir(
            skills_dir,
            "github",
            _make_skill_md(
                "github",
                "GitHub CLI",
                metadata={"nanobot": {"requires": {"bins": ["nonexistent-binary-xyz"]}}},
            ),
        )

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        upsert_call = mock_bridge.mutation.call_args_list[0]
        args = upsert_call[0][1]
        assert args["available"] is False
        assert "nonexistent-binary-xyz" in (args.get("requires") or "")

    def test_empty_skills_dir(self, tmp_path):
        """No error when skills directory is empty."""
        from mc.runtime.gateway import sync_skills

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        # Should call deactivateExcept with empty list
        deactivate_calls = [
            c for c in mock_bridge.mutation.call_args_list if c[0][0] == "skills:deactivateExcept"
        ]
        assert len(deactivate_calls) == 1
        assert deactivate_calls[0][0][1]["active_names"] == []

    def test_metadata_json_stored(self, tmp_path):
        """Metadata from frontmatter should be stored as JSON string."""
        from mc.runtime.gateway import sync_skills

        meta = {"nanobot": {"emoji": "\U0001f419", "requires": {"bins": ["gh"]}}}
        skills_dir = tmp_path / "skills"
        _create_skill_dir(
            skills_dir,
            "github",
            _make_skill_md(
                "github",
                "GitHub",
                metadata=meta,
            ),
        )

        mock_bridge = MagicMock()
        sync_skills(mock_bridge, builtin_skills_dir=skills_dir)

        upsert_call = mock_bridge.mutation.call_args_list[0]
        args = upsert_call[0][1]
        assert args["metadata"] is not None
        # metadata should be the raw JSON string from frontmatter
        assert isinstance(args["metadata"], str)
