"""Tests for artifact_collector module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from mc.application.execution.artifact_collector import (
    _human_size,
    collect_output_artifacts,
    snapshot_output_dir,
)


class TestHumanSize:
    """Tests for _human_size helper."""

    def test_bytes_under_1mb(self) -> None:
        assert _human_size(512 * 1024) == "512 KB"

    def test_zero_bytes(self) -> None:
        assert _human_size(0) == "0 KB"

    def test_over_1mb(self) -> None:
        assert _human_size(2 * 1024 * 1024) == "2.0 MB"


class TestSnapshotOutputDir:
    """Tests for snapshot_output_dir."""

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        """Snapshot of a non-existent directory returns empty dict."""
        # Use a task ID that won't have a real directory
        result = snapshot_output_dir("nonexistent_task_zzz_12345")
        assert result == {}

    def test_snapshot_captures_files(self, tmp_path: Path) -> None:
        """Snapshot captures files in the output directory."""
        tasks_dir = tmp_path / "tasks"
        output_dir = tasks_dir / "test_task" / "output"
        output_dir.mkdir(parents=True)
        (output_dir / "data.json").write_text("{}")

        with patch(
            "mc.application.execution.artifact_collector.get_tasks_dir",
            return_value=tasks_dir,
        ):
            result = snapshot_output_dir("test_task")

        assert "output/data.json" in result


class TestCollectOutputArtifacts:
    """Tests for collect_output_artifacts."""

    def test_no_output_dir_returns_empty(self) -> None:
        result = collect_output_artifacts("nonexistent_task_zzz_12345", {})
        assert result == []

    def test_none_pre_snapshot(self) -> None:
        result = collect_output_artifacts("nonexistent_task_zzz_12345", None)
        assert result == []

    def test_new_files_detected(self, tmp_path: Path) -> None:
        """New files (not in pre-snapshot) are marked as created."""
        tasks_dir = tmp_path / "tasks"
        output_dir = tasks_dir / "test_task" / "output"
        output_dir.mkdir(parents=True)
        report = output_dir / "report.pdf"
        report.write_bytes(b"x" * 2048)

        with patch(
            "mc.application.execution.artifact_collector.get_tasks_dir",
            return_value=tasks_dir,
        ):
            result = collect_output_artifacts("test_task", {})

        assert len(result) == 1
        assert result[0]["action"] == "created"
        assert result[0]["path"] == "output/report.pdf"
        assert "PDF" in result[0]["description"]

    def test_modified_files_detected(self, tmp_path: Path) -> None:
        """Files with newer mtime are marked as modified."""
        tasks_dir = tmp_path / "tasks"
        output_dir = tasks_dir / "test_task" / "output"
        output_dir.mkdir(parents=True)
        data_file = output_dir / "data.json"
        data_file.write_text("{}")

        # Pre-snapshot with old mtime
        old_mtime = data_file.stat().st_mtime - 10
        pre_snapshot = {"output/data.json": old_mtime}

        with patch(
            "mc.application.execution.artifact_collector.get_tasks_dir",
            return_value=tasks_dir,
        ):
            result = collect_output_artifacts("test_task", pre_snapshot)

        assert len(result) == 1
        assert result[0]["action"] == "modified"

    def test_unchanged_files_not_included(self, tmp_path: Path) -> None:
        """Files with same mtime are not included in artifacts."""
        tasks_dir = tmp_path / "tasks"
        output_dir = tasks_dir / "test_task" / "output"
        output_dir.mkdir(parents=True)
        data_file = output_dir / "data.json"
        data_file.write_text("{}")

        # Pre-snapshot with current mtime (or future to be safe)
        current_mtime = data_file.stat().st_mtime + 10
        pre_snapshot = {"output/data.json": current_mtime}

        with patch(
            "mc.application.execution.artifact_collector.get_tasks_dir",
            return_value=tasks_dir,
        ):
            result = collect_output_artifacts("test_task", pre_snapshot)

        assert len(result) == 0
