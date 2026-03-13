"""Tests for file_enricher module."""

from __future__ import annotations

from mc.application.execution.file_enricher import (
    _human_size,
    build_file_context,
    build_file_manifest,
    resolve_task_dirs,
)


class TestHumanSize:
    """Tests for _human_size helper."""

    def test_bytes_under_1mb(self) -> None:
        assert _human_size(512 * 1024) == "512 KB"

    def test_zero_bytes(self) -> None:
        assert _human_size(0) == "0 KB"

    def test_over_1mb(self) -> None:
        result = _human_size(2 * 1024 * 1024)
        assert result == "2.0 MB"

    def test_fractional_mb(self) -> None:
        result = _human_size(1536 * 1024)  # 1.5 MB
        assert result == "1.5 MB"


class TestBuildFileManifest:
    """Tests for build_file_manifest."""

    def test_empty_files(self) -> None:
        assert build_file_manifest([]) == []

    def test_single_file(self) -> None:
        raw = [{"name": "doc.pdf", "type": "application/pdf", "size": 1024}]
        result = build_file_manifest(raw)
        assert len(result) == 1
        assert result[0]["name"] == "doc.pdf"
        assert result[0]["type"] == "application/pdf"
        assert result[0]["size"] == 1024
        assert result[0]["subfolder"] == "attachments"

    def test_missing_fields_use_defaults(self) -> None:
        raw = [{}]
        result = build_file_manifest(raw)
        assert result[0]["name"] == "unknown"
        assert result[0]["type"] == "application/octet-stream"
        assert result[0]["size"] == 0
        assert result[0]["subfolder"] == "attachments"

    def test_custom_subfolder(self) -> None:
        raw = [{"name": "data.csv", "subfolder": "uploads"}]
        result = build_file_manifest(raw)
        assert result[0]["subfolder"] == "uploads"

    def test_multiple_files(self) -> None:
        raw = [
            {"name": "a.txt", "size": 100},
            {"name": "b.pdf", "size": 200},
        ]
        result = build_file_manifest(raw)
        assert len(result) == 2
        assert result[0]["name"] == "a.txt"
        assert result[1]["name"] == "b.pdf"


class TestResolveTaskDirs:
    """Tests for resolve_task_dirs."""

    def test_returns_tuple(self) -> None:
        files_dir, output_dir = resolve_task_dirs("task_123")
        assert isinstance(files_dir, str)
        assert isinstance(output_dir, str)

    def test_output_dir_is_subdirectory(self) -> None:
        files_dir, output_dir = resolve_task_dirs("task_123")
        assert output_dir.startswith(files_dir)
        assert output_dir.endswith("/output")

    def test_uses_nanobot_tasks_dir(self) -> None:
        files_dir, _ = resolve_task_dirs("task_123")
        assert ".nanobot/tasks/" in files_dir


class TestBuildFileContextTask:
    """Tests for build_file_context in task mode."""

    def test_empty_manifest(self) -> None:
        result = build_file_context([], "/tasks/abc", "/tasks/abc/output")
        assert "Task workspace: /tasks/abc" in result
        assert "output" in result
        assert "Do NOT save output files" in result

    def test_with_manifest(self) -> None:
        manifest = [
            {"name": "doc.pdf", "subfolder": "attachments", "size": 2048},
        ]
        result = build_file_context(manifest, "/tasks/abc", "/tasks/abc/output")
        assert "1 attached file(s)" in result
        assert "doc.pdf" in result
        assert "attachments" in result

    def test_multiple_files_in_manifest(self) -> None:
        manifest = [
            {"name": "a.txt", "subfolder": "attachments", "size": 100},
            {"name": "b.pdf", "subfolder": "attachments", "size": 200},
        ]
        result = build_file_context(manifest, "/tasks/abc", "/tasks/abc/output")
        assert "2 attached file(s)" in result
        assert "a.txt" in result
        assert "b.pdf" in result

    def test_distinguishes_memory_artifacts_and_output(self) -> None:
        result = build_file_context(
            [],
            "/tasks/abc",
            "/tasks/abc/output",
            memory_dir="/agents/dev-agent/memory",
            artifacts_dir="/boards/default/artifacts",
        )

        assert (
            "Store long-term facts and consolidated history in: /agents/dev-agent/memory" in result
        )
        assert "Store reusable board artifacts in: /boards/default/artifacts" in result
        assert "Save task deliverables to: /tasks/abc/output" in result


class TestBuildFileContextStep:
    """Tests for build_file_context in step mode."""

    def test_step_format(self) -> None:
        result = build_file_context(
            [],
            "/tasks/abc",
            "/tasks/abc/output",
            is_step=True,
            step_title="Analyze data",
            step_description="Analyze the CSV data",
            task_title="Data Project",
        )
        assert 'You are executing step: "Analyze data"' in result
        assert "Step description: Analyze the CSV data" in result
        assert 'This step is part of task: "Data Project"' in result
        assert "Task workspace: /tasks/abc" in result

    def test_step_with_file_manifest(self) -> None:
        manifest = [
            {"name": "data.csv", "subfolder": "attachments", "size": 5000},
        ]
        result = build_file_context(
            manifest,
            "/tasks/abc",
            "/tasks/abc/output",
            is_step=True,
            step_title="Process",
            step_description="Process files",
            task_title="Task",
        )
        assert "1 file(s) in its manifest" in result
        assert "data.csv" in result
        assert "Review the file manifest" in result
