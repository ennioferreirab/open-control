"""Write skill SKILL.md files to the runtime workspace on disk."""

from __future__ import annotations

from pathlib import Path

from mc.infrastructure.runtime_home import get_runtime_path


def write_skill_to_disk(
    name: str,
    description: str,
    content: str,
    *,
    always: bool = False,
    metadata: str | None = None,
) -> Path:
    """Write a SKILL.md file to ``~/.nanobot/workspace/skills/<name>/SKILL.md``.

    Creates the directory if it doesn't exist.  Writes atomically via a
    temporary file to avoid partial reads.

    Args:
        name: Skill name slug.
        description: What the skill does and when to use it.
        content: The SKILL.md body (frontmatter-stripped).
        always: Whether the skill is always loaded.
        metadata: Optional JSON metadata string.

    Returns:
        Path to the written SKILL.md file.
    """
    skill_dir = get_runtime_path("workspace", "skills", name)
    skill_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"name: {name}",
        f'description: "{_escape_yaml_string(description)}"',
    ]
    if always:
        lines.append("always: true")
    if metadata is not None:
        lines.append(f"metadata: {metadata}")
    lines.append("---")
    lines.append("")

    full_content = "\n".join(lines) + "\n" + content
    if not full_content.endswith("\n"):
        full_content += "\n"

    target = skill_dir / "SKILL.md"
    tmp = skill_dir / ".SKILL.md.tmp"
    tmp.write_text(full_content, encoding="utf-8")
    tmp.rename(target)

    return target


def _escape_yaml_string(value: str) -> str:
    """Escape double quotes inside a YAML double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
