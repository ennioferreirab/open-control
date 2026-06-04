"""Unit tests for media support in send_message IPC handler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from claude_code.ipc_server import MCSocketServer

pytestmark = pytest.mark.asyncio


class TestSendMessageMediaFallback:
    """Tests for media file auto-sync to task output dir in bridge fallback path."""

    async def test_media_copied_to_output_dir_on_fallback(self, tmp_path):
        """When fallback path is taken with media, files are copied to task output dir."""
        # Create a temp media file
        src_file = tmp_path / "result.png"
        src_file.write_bytes(b"fake-png-data")

        bridge = MagicMock()
        bridge.send_message = MagicMock()
        server = MCSocketServer(bridge, bus=None)

        task_id = "test-task-123"
        from mc.types import task_safe_id

        safe_id = task_safe_id(task_id)
        tasks_root = tmp_path / "tasks"
        output_dir = tasks_root / safe_id / "output"

        with patch("mc.infrastructure.runtime_home.get_tasks_dir", return_value=tasks_root):
            result = await server._handle_send_message(
                content="Here are the results",
                media=[str(src_file)],
                task_id=task_id,
            )

        assert result["status"] == "Message sent"
        copied = output_dir / "result.png"
        assert copied.exists()
        assert copied.read_bytes() == b"fake-png-data"

    async def test_media_missing_file_skipped(self, tmp_path):
        """Non-existent media paths are silently skipped."""
        bridge = MagicMock()
        bridge.send_message = MagicMock()
        server = MCSocketServer(bridge, bus=None)

        task_id = "test-task-456"
        from mc.types import task_safe_id

        safe_id = task_safe_id(task_id)
        output_dir = tmp_path / ".open-control" / "tasks" / safe_id / "output"

        with patch.object(Path, "home", return_value=tmp_path):
            result = await server._handle_send_message(
                content="Some text",
                media=["/nonexistent/file.png"],
                task_id=task_id,
            )

        assert result["status"] == "Message sent"
        # Output dir may or may not be created, but no file should exist
        if output_dir.exists():
            assert list(output_dir.iterdir()) == []

    async def test_media_content_appended_with_filenames(self, tmp_path):
        """Content posted to bridge includes 'Attached files:' with file names."""
        src_file = tmp_path / "chart.pdf"
        src_file.write_bytes(b"pdf-data")

        bridge = MagicMock()
        bridge.send_message = MagicMock()
        server = MCSocketServer(bridge, bus=None)

        with patch.object(Path, "home", return_value=tmp_path):
            result = await server._handle_send_message(
                content="Report ready",
                media=[str(src_file)],
                task_id="task-789",
            )

        assert result["status"] == "Message sent"
        # Check the content arg passed to bridge.send_message
        call_args = bridge.send_message.call_args
        posted_content = call_args[0][3]  # 4th positional arg is content
        assert "Attached files: chart.pdf" in posted_content

    async def test_media_no_copy_when_no_task_id(self):
        """When task_id is None, no media copy is attempted (no crash)."""
        # Without task_id AND bridge, it will hit the H3 error path
        server_no_bridge = MCSocketServer(bridge=None, bus=None)
        result = await server_no_bridge._handle_send_message(
            content="orphaned media",
            media=["/tmp/file.png"],
        )
        # Should get error since no task_id, no channel/chat_id
        assert "error" in result

    async def test_media_multiple_files_mixed_existence(self, tmp_path):
        """Fallback copies existing files and skips missing ones."""
        existing = tmp_path / "chart.png"
        existing.write_bytes(b"png-data")

        bridge = MagicMock()
        bridge.send_message = MagicMock()
        server = MCSocketServer(bridge, bus=None)

        task_id = "multi-file-task"
        tasks_root = tmp_path / "tasks"

        with patch("mc.infrastructure.runtime_home.get_tasks_dir", return_value=tasks_root):
            result = await server._handle_send_message(
                content="Mixed results",
                media=[str(existing), "/nonexistent/missing.pdf"],
                task_id=task_id,
            )

        assert result["status"] == "Message sent"

        from mc.types import task_safe_id

        safe_id = task_safe_id(task_id)
        output_dir = tasks_root / safe_id / "output"
        assert (output_dir / "chart.png").exists()
        assert not (output_dir / "missing.pdf").exists()

        call_args = bridge.send_message.call_args
        posted_content = call_args[0][3]
        assert "Attached files: chart.png" in posted_content
        assert "missing.pdf" not in posted_content
