"""Tests for mc.infrastructure.config — config, env resolution, path utilities."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestAgentsDir:
    """AGENTS_DIR constant."""

    def test_agents_dir_is_path(self) -> None:
        from mc.infrastructure.config import AGENTS_DIR

        assert isinstance(AGENTS_DIR, Path)

    def test_agents_dir_under_nanobot(self) -> None:
        from mc.infrastructure.config import AGENTS_DIR

        assert AGENTS_DIR == Path.home() / ".nanobot" / "agents"


class TestResolveConvexUrl:
    """_resolve_convex_url env and file resolution."""

    def test_returns_env_var_when_set(self) -> None:
        from mc.infrastructure.config import _resolve_convex_url

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            assert _resolve_convex_url() == "https://test.convex.cloud"

    def test_returns_none_when_no_env_no_file(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _resolve_convex_url

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CONVEX_URL", None)
            assert _resolve_convex_url(dashboard_dir=tmp_path) is None

    def test_reads_from_env_local(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _resolve_convex_url

        env_local = tmp_path / ".env.local"
        env_local.write_text('NEXT_PUBLIC_CONVEX_URL="https://from-file.convex.cloud"')
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CONVEX_URL", None)
            result = _resolve_convex_url(dashboard_dir=tmp_path)
            assert result == "https://from-file.convex.cloud"

    def test_env_var_takes_precedence_over_file(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _resolve_convex_url

        env_local = tmp_path / ".env.local"
        env_local.write_text('NEXT_PUBLIC_CONVEX_URL="https://from-file.convex.cloud"')
        with patch.dict(os.environ, {"CONVEX_URL": "https://from-env.convex.cloud"}):
            result = _resolve_convex_url(dashboard_dir=tmp_path)
            assert result == "https://from-env.convex.cloud"


class TestResolveAdminKey:
    """_resolve_admin_key file resolution."""

    def test_returns_none_when_no_file(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _resolve_admin_key

        assert _resolve_admin_key(dashboard_dir=tmp_path) is None

    def test_reads_from_env_local(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _resolve_admin_key

        env_local = tmp_path / ".env.local"
        env_local.write_text('CONVEX_ADMIN_KEY="test-admin-key-123"')
        result = _resolve_admin_key(dashboard_dir=tmp_path)
        assert result == "test-admin-key-123"


class TestFilterAgentFields:
    """filter_agent_fields strips unknown keys."""

    def test_strips_unknown_fields(self) -> None:
        from mc.infrastructure.config import filter_agent_fields

        data = {
            "name": "test-agent",
            "role": "tester",
            "creation_time": 12345,  # unknown field
            "_extra": "should be stripped",
        }
        result = filter_agent_fields(data)
        assert "name" in result
        assert "role" in result
        assert "creation_time" not in result
        assert "_extra" not in result

    def test_preserves_known_fields(self) -> None:
        from mc.infrastructure.config import filter_agent_fields

        data = {"name": "test-agent", "role": "tester", "model": "anthropic/claude-sonnet"}
        result = filter_agent_fields(data)
        assert result == data


class TestParseUtcTimestamp:
    """_parse_utc_timestamp handles ISO 8601 variants."""

    def test_parses_z_suffix(self) -> None:
        from mc.infrastructure.config import _parse_utc_timestamp

        result = _parse_utc_timestamp("2026-01-01T00:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_parses_offset_suffix(self) -> None:
        from mc.infrastructure.config import _parse_utc_timestamp

        result = _parse_utc_timestamp("2026-01-01T00:00:00+00:00")
        assert result is not None
        assert result.year == 2026

    def test_parses_naive_as_utc(self) -> None:
        from datetime import timezone

        from mc.infrastructure.config import _parse_utc_timestamp

        result = _parse_utc_timestamp("2026-01-01T00:00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_returns_none_for_empty_string(self) -> None:
        from mc.infrastructure.config import _parse_utc_timestamp

        assert _parse_utc_timestamp("") is None

    def test_returns_none_for_invalid_string(self) -> None:
        from mc.infrastructure.config import _parse_utc_timestamp

        assert _parse_utc_timestamp("not-a-date") is None

    def test_returns_none_for_non_string(self) -> None:
        from mc.infrastructure.config import _parse_utc_timestamp

        assert _parse_utc_timestamp(12345) is None  # type: ignore[arg-type]


class TestReadFileOrNone:
    """_read_file_or_none file reading helper."""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _read_file_or_none

        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert _read_file_or_none(f) == "hello world"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _read_file_or_none

        assert _read_file_or_none(tmp_path / "missing.txt") is None


class TestReadSessionData:
    """_read_session_data JSONL concatenation."""

    def test_reads_jsonl_files(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _read_session_data

        (tmp_path / "a.jsonl").write_text('{"line":1}')
        (tmp_path / "b.jsonl").write_text('{"line":2}')
        result = _read_session_data(tmp_path)
        assert result is not None
        assert '{"line":1}' in result
        assert '{"line":2}' in result

    def test_returns_none_for_missing_dir(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _read_session_data

        assert _read_session_data(tmp_path / "nonexistent") is None

    def test_returns_none_for_empty_dir(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _read_session_data

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert _read_session_data(empty_dir) is None

    def test_ignores_non_jsonl_files(self, tmp_path: Path) -> None:
        from mc.infrastructure.config import _read_session_data

        (tmp_path / "data.txt").write_text("not jsonl")
        (tmp_path / "data.jsonl").write_text('{"ok":true}')
        result = _read_session_data(tmp_path)
        assert result == '{"ok":true}'
