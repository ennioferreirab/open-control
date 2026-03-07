"""Tests for startup skill distribution — Story SK.1.

Validates _distribute_builtin_skills() behavior:
- copies new skill dirs (those with SKILL.md) to workspace
- skips existing workspace skills (never overwrites)
- skips directories without SKILL.md
- creates workspace skills dir if missing
- handles missing source dirs gracefully
"""

import logging
from pathlib import Path

import pytest


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    """Create a temporary workspace skills directory."""
    skills_dir = tmp_path / "workspace" / "skills"
    skills_dir.mkdir(parents=True)
    return skills_dir


@pytest.fixture
def source_dir_with_skills(tmp_path: Path) -> Path:
    """Create a source directory with two skill subdirs (with SKILL.md) and one non-skill subdir."""
    src = tmp_path / "source_skills"
    src.mkdir()

    # Skill A — has SKILL.md
    skill_a = src / "skill-alpha"
    skill_a.mkdir()
    (skill_a / "SKILL.md").write_text("---\nname: skill-alpha\n---\nAlpha skill body.")
    (skill_a / "helpers.py").write_text("# helper code")

    # Skill B — has SKILL.md
    skill_b = src / "skill-beta"
    skill_b.mkdir()
    (skill_b / "SKILL.md").write_text("---\nname: skill-beta\n---\nBeta skill body.")

    # Non-skill dir — no SKILL.md
    non_skill = src / "not-a-skill"
    non_skill.mkdir()
    (non_skill / "README.md").write_text("This is not a skill.")

    return src


class TestDistributeBuiltinSkills:
    """Tests for mc.runtime.gateway._distribute_builtin_skills."""

    def test_copies_new_skill_with_skill_md(
        self, workspace_dir: Path, source_dir_with_skills: Path
    ):
        """A skill directory containing SKILL.md is copied to workspace."""
        from mc.runtime.gateway import _distribute_builtin_skills

        _distribute_builtin_skills(workspace_dir, source_dir_with_skills)

        target_alpha = workspace_dir / "skill-alpha"
        assert target_alpha.is_dir()
        assert (target_alpha / "SKILL.md").exists()
        assert (target_alpha / "helpers.py").exists()
        # Verify content integrity
        assert "Alpha skill body" in (target_alpha / "SKILL.md").read_text()

    def test_copies_multiple_skills(
        self, workspace_dir: Path, source_dir_with_skills: Path
    ):
        """All skill directories (those with SKILL.md) are copied."""
        from mc.runtime.gateway import _distribute_builtin_skills

        _distribute_builtin_skills(workspace_dir, source_dir_with_skills)

        assert (workspace_dir / "skill-alpha").is_dir()
        assert (workspace_dir / "skill-beta").is_dir()

    def test_skips_existing_workspace_skill(
        self, workspace_dir: Path, source_dir_with_skills: Path
    ):
        """Existing workspace skills are NEVER overwritten (preserves user customizations)."""
        from mc.runtime.gateway import _distribute_builtin_skills

        # Pre-create skill-alpha with custom content
        existing = workspace_dir / "skill-alpha"
        existing.mkdir()
        (existing / "SKILL.md").write_text("User-customized content.")

        _distribute_builtin_skills(workspace_dir, source_dir_with_skills)

        # Verify original content is preserved
        assert (existing / "SKILL.md").read_text() == "User-customized content."
        # helpers.py should NOT exist because we didn't overwrite
        assert not (existing / "helpers.py").exists()

    def test_skips_directory_without_skill_md(
        self, workspace_dir: Path, source_dir_with_skills: Path
    ):
        """Directories without SKILL.md are not copied."""
        from mc.runtime.gateway import _distribute_builtin_skills

        _distribute_builtin_skills(workspace_dir, source_dir_with_skills)

        assert not (workspace_dir / "not-a-skill").exists()

    def test_creates_workspace_skills_dir_if_missing(
        self, tmp_path: Path, source_dir_with_skills: Path
    ):
        """workspace_skills_dir is created if it doesn't exist."""
        from mc.runtime.gateway import _distribute_builtin_skills

        missing_dir = tmp_path / "nonexistent" / "skills"
        assert not missing_dir.exists()

        _distribute_builtin_skills(missing_dir, source_dir_with_skills)

        assert missing_dir.is_dir()
        assert (missing_dir / "skill-alpha").is_dir()

    def test_handles_missing_source_dir_gracefully(
        self, workspace_dir: Path, tmp_path: Path
    ):
        """If a source_dir doesn't exist, it's skipped without error."""
        from mc.runtime.gateway import _distribute_builtin_skills

        missing_source = tmp_path / "does_not_exist"
        # Should not raise
        _distribute_builtin_skills(workspace_dir, missing_source)

        # Workspace should still be fine, just empty
        assert workspace_dir.is_dir()

    def test_multiple_source_dirs(
        self, workspace_dir: Path, tmp_path: Path
    ):
        """Skills from multiple source directories are all distributed."""
        from mc.runtime.gateway import _distribute_builtin_skills

        # Source 1
        src1 = tmp_path / "src1"
        src1.mkdir()
        (src1 / "skill-one").mkdir()
        (src1 / "skill-one" / "SKILL.md").write_text("Skill one.")

        # Source 2
        src2 = tmp_path / "src2"
        src2.mkdir()
        (src2 / "skill-two").mkdir()
        (src2 / "skill-two" / "SKILL.md").write_text("Skill two.")

        _distribute_builtin_skills(workspace_dir, src1, src2)

        assert (workspace_dir / "skill-one").is_dir()
        assert (workspace_dir / "skill-two").is_dir()

    def test_logs_distributed_skills(
        self, workspace_dir: Path, source_dir_with_skills: Path, caplog
    ):
        """Each distributed skill is logged with its name."""
        from mc.runtime.gateway import _distribute_builtin_skills

        with caplog.at_level(logging.INFO, logger="mc.infrastructure.agent_bootstrap"):
            _distribute_builtin_skills(workspace_dir, source_dir_with_skills)

        log_text = caplog.text
        assert "skill-alpha" in log_text
        assert "skill-beta" in log_text

    def test_does_not_log_skipped_non_skill_dirs(
        self, workspace_dir: Path, source_dir_with_skills: Path, caplog
    ):
        """Non-skill directories are not logged as distributed."""
        from mc.runtime.gateway import _distribute_builtin_skills

        with caplog.at_level(logging.DEBUG, logger="mc.infrastructure.agent_bootstrap"):
            _distribute_builtin_skills(workspace_dir, source_dir_with_skills)

        # "not-a-skill" should not appear in logs as distributed
        distributed_lines = [
            r for r in caplog.records
            if "Distribut" in r.message and "not-a-skill" in r.message
        ]
        assert len(distributed_lines) == 0

    def test_handles_source_dir_with_files_not_dirs(
        self, workspace_dir: Path, tmp_path: Path
    ):
        """Files (not directories) in source_dir are ignored."""
        from mc.runtime.gateway import _distribute_builtin_skills

        src = tmp_path / "source"
        src.mkdir()
        (src / "plain_file.txt").write_text("not a directory")

        # Should not raise
        _distribute_builtin_skills(workspace_dir, src)
