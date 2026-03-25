"""Tests for mc.infrastructure.skill_disk_writer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mc.infrastructure.skill_disk_writer import write_skill_to_disk


@pytest.fixture()
def workspace(tmp_path):
    """Patch get_runtime_path to use a temp directory."""
    with patch(
        "mc.infrastructure.skill_disk_writer.get_runtime_path",
        side_effect=lambda *parts: tmp_path.joinpath(*parts),
    ):
        yield tmp_path


class TestWriteSkillToDisk:
    def test_writes_skill_md_with_frontmatter(self, workspace):
        path = write_skill_to_disk(
            name="my-skill",
            description="Does something useful",
            content="# My Skill\n\nDo the thing.",
        )

        assert path.exists()
        text = path.read_text()
        assert text.startswith("---\n")
        assert "name: my-skill\n" in text
        assert 'description: "Does something useful"\n' in text
        assert "---\n\n# My Skill\n\nDo the thing.\n" in text

    def test_creates_directory_if_not_exists(self, workspace):
        path = write_skill_to_disk(
            name="new-skill",
            description="Brand new",
            content="Content here.",
        )

        assert path.parent.is_dir()
        assert path.parent.name == "new-skill"

    def test_overwrites_existing_skill_md(self, workspace):
        write_skill_to_disk(name="x", description="v1", content="old")
        path = write_skill_to_disk(name="x", description="v2", content="new")

        text = path.read_text()
        assert 'description: "v2"' in text
        assert "new" in text
        assert "old" not in text

    def test_includes_always_field_when_true(self, workspace):
        path = write_skill_to_disk(name="a", description="d", content="c", always=True)

        text = path.read_text()
        assert "always: true\n" in text

    def test_omits_always_field_when_false(self, workspace):
        path = write_skill_to_disk(name="a", description="d", content="c", always=False)

        text = path.read_text()
        assert "always" not in text

    def test_includes_metadata_field_when_provided(self, workspace):
        path = write_skill_to_disk(
            name="a",
            description="d",
            content="c",
            metadata='{"category":"tools"}',
        )

        text = path.read_text()
        assert 'metadata: {"category":"tools"}\n' in text

    def test_returns_path_to_written_file(self, workspace):
        path = write_skill_to_disk(name="ret", description="d", content="c")

        assert path == workspace / "workspace" / "skills" / "ret" / "SKILL.md"

    def test_description_with_special_chars_is_quoted(self, workspace):
        path = write_skill_to_disk(
            name="a",
            description='Has "quotes" and colons: here',
            content="c",
        )

        text = path.read_text()
        assert r'description: "Has \"quotes\" and colons: here"' in text

    def test_no_temp_file_left_behind(self, workspace):
        write_skill_to_disk(name="clean", description="d", content="c")

        skill_dir = workspace / "workspace" / "skills" / "clean"
        assert not (skill_dir / ".SKILL.md.tmp").exists()

    def test_content_ends_with_newline(self, workspace):
        path = write_skill_to_disk(name="a", description="d", content="no trailing")

        text = path.read_text()
        assert text.endswith("\n")
