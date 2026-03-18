"""Tests for artifact_collector module."""

from __future__ import annotations

from pathlib import Path

import pytest

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

    def test_snapshot_captures_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Snapshot captures files in the output directory."""
        # Create a fake output directory structure
        task_dir = tmp_path / "tasks" / "test_task" / "output"
        task_dir.mkdir(parents=True)
        (task_dir / "report.pdf").write_text("content")

        # Monkeypatch Path.home to use tmp_path parent
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        nanobot_output = tmp_path / "home" / ".nanobot" / "tasks" / "test_task" / "output"
        nanobot_output.mkdir(parents=True)
        (nanobot_output / "data.json").write_text("{}")

        from mc.types import task_safe_id

        # The task_safe_id will transform the ID
        safe_id = task_safe_id("test_task")
        assert safe_id == "test_task"

        result = snapshot_output_dir("test_task")
        # Since we monkeypatched home(), this should find our files
        assert "output/data.json" in result


class TestCollectOutputArtifacts:
    """Tests for collect_output_artifacts."""

    def test_no_output_dir_returns_empty(self) -> None:
        result = collect_output_artifacts("nonexistent_task_zzz_12345", {})
        assert result == []

    def test_none_pre_snapshot(self) -> None:
        result = collect_output_artifacts("nonexistent_task_zzz_12345", None)
        assert result == []

    def test_new_files_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """New files (not in pre-snapshot) are marked as created."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        output_dir = tmp_path / ".nanobot" / "tasks" / "test_task" / "output"
        output_dir.mkdir(parents=True)
        report = output_dir / "report.pdf"
        report.write_bytes(b"x" * 2048)

        result = collect_output_artifacts("test_task", {})
        assert len(result) == 1
        assert result[0]["action"] == "created"
        assert result[0]["path"] == "output/report.pdf"
        assert "PDF" in result[0]["description"]

    def test_modified_files_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Files with newer mtime are marked as modified."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        output_dir = tmp_path / ".nanobot" / "tasks" / "test_task" / "output"
        output_dir.mkdir(parents=True)
        data_file = output_dir / "data.json"
        data_file.write_text("{}")

        # Pre-snapshot with old mtime
        old_mtime = data_file.stat().st_mtime - 10
        pre_snapshot = {"output/data.json": old_mtime}

        result = collect_output_artifacts("test_task", pre_snapshot)
        assert len(result) == 1
        assert result[0]["action"] == "modified"

    def test_unchanged_files_not_included(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Files with same mtime are not included in artifacts."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        output_dir = tmp_path / ".nanobot" / "tasks" / "test_task" / "output"
        output_dir.mkdir(parents=True)
        data_file = output_dir / "data.json"
        data_file.write_text("{}")

        # Pre-snapshot with current mtime (or future to be safe)
        current_mtime = data_file.stat().st_mtime + 10
        pre_snapshot = {"output/data.json": current_mtime}

        result = collect_output_artifacts("test_task", pre_snapshot)
        assert len(result) == 0
