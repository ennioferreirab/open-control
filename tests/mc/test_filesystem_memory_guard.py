from __future__ import annotations

import pytest
from nanobot.agent.tools.filesystem import EditFileTool, WriteFileTool


@pytest.mark.asyncio
async def test_write_file_blocks_non_contract_memory_path(tmp_path):
    tool = WriteFileTool(workspace=tmp_path, allowed_dir=tmp_path)

    result = await tool.execute("memory/notes.md", "artifact")

    assert "restricted to memory/MEMORY.md and memory/HISTORY.md" in result
    assert "artifacts/" in result
    assert "reusable artifacts" in result


@pytest.mark.asyncio
async def test_write_file_allows_memory_md(tmp_path):
    tool = WriteFileTool(workspace=tmp_path, allowed_dir=tmp_path)

    result = await tool.execute("memory/MEMORY.md", "facts")

    assert "Successfully wrote" in result
    assert (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8") == "facts"


@pytest.mark.asyncio
async def test_edit_file_blocks_non_contract_memory_path(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "rogue.md").write_text("before", encoding="utf-8")
    tool = EditFileTool(workspace=tmp_path, allowed_dir=tmp_path)

    result = await tool.execute("memory/rogue.md", "before", "after")

    assert "restricted to memory/MEMORY.md and memory/HISTORY.md" in result
    assert "artifacts/" in result
    assert (memory_dir / "rogue.md").read_text(encoding="utf-8") == "before"
