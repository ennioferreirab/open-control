"""Unit tests for CLI status and docs commands (Story 7.5)."""

import os
from unittest.mock import patch

from typer.testing import CliRunner

from mc.cli import mc_app

runner = CliRunner()


# ── status: MC not running ──────────────────────────────────────────


class TestStatusNotRunning:
    def test_no_pid_file(self, tmp_path):
        fake_pid = tmp_path / "mc.pid"
        with patch("mc.cli.PID_FILE", fake_pid):
            result = runner.invoke(mc_app, ["status"])

        assert result.exit_code == 0
        assert "Open Control is not running" in result.output
        assert "open-control mc start" in result.output

    def test_stale_pid_file(self, tmp_path):
        fake_pid = tmp_path / "mc.pid"
        fake_pid.write_text("999999999")  # non-existent PID

        with patch("mc.cli.PID_FILE", fake_pid):
            result = runner.invoke(mc_app, ["status"])

        assert result.exit_code == 0
        assert "stale PID file" in result.output
        assert not fake_pid.exists()  # should be cleaned up

    def test_invalid_pid_file(self, tmp_path):
        fake_pid = tmp_path / "mc.pid"
        fake_pid.write_text("not-a-number")

        with patch("mc.cli.PID_FILE", fake_pid):
            result = runner.invoke(mc_app, ["status"])

        assert result.exit_code == 0
        assert "stale PID file" in result.output


# ── status: MC running ──────────────────────────────────────────────


class TestStatusRunning:
    def _setup_running_pid(self, tmp_path):
        """Create a PID file pointing to the current process."""
        fake_pid = tmp_path / "mc.pid"
        fake_pid.write_text(str(os.getpid()))
        return fake_pid

    @patch("mc.bridge.ConvexClient")
    def test_displays_running_status(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "Open Control is running" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_displays_dashboard_url(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "http://localhost:3000" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_displays_uptime(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "Uptime:" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_displays_agent_table(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.side_effect = [
            # agents:list
            [
                {
                    "name": "dev-agent",
                    "status": "active",
                    "lastActiveAt": "2026-02-23T10:00:00Z",
                },
                {
                    "name": "reviewer",
                    "status": "idle",
                    "lastActiveAt": None,
                },
            ],
            # tasks:list
            [],
        ]

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "dev-agent" in result.output
        assert "reviewer" in result.output
        assert "Agents" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_displays_no_agents_message(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.side_effect = [
            [],  # agents:list
            [],  # tasks:list
        ]

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "No agents registered" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_displays_task_counts(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.side_effect = [
            [],  # agents:list
            # tasks:list
            [
                {"status": "inbox"},
                {"status": "inbox"},
                {"status": "in_progress"},
                {"status": "done"},
                {"status": "done"},
                {"status": "done"},
            ],
        ]

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "Tasks" in result.output
        assert "Total tasks: 6" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_closes_bridge(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                runner.invoke(mc_app, ["status"])

        mock_client.close.assert_called_once()

    @patch("mc.bridge.ConvexClient")
    def test_handles_query_error(self, MockClient, tmp_path):
        fake_pid = self._setup_running_pid(tmp_path)
        mock_client = MockClient.return_value
        mock_client.query.side_effect = Exception("Connection refused")

        with patch("mc.cli.PID_FILE", fake_pid):
            with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
                result = runner.invoke(mc_app, ["status"])

        assert "Error querying system state" in result.output
        mock_client.close.assert_called_once()


# ── docs command ────────────────────────────────────────────────────


class TestDocsCommand:
    def test_docs_no_convex_dir(self, tmp_path):
        with patch("mc.cli._find_dashboard_dir", return_value=tmp_path):
            result = runner.invoke(mc_app, ["docs"])

        assert result.exit_code == 1
        assert "Convex directory not found" in result.output

    def test_docs_displays_schema_tables(self, tmp_path):
        convex_dir = tmp_path / "convex"
        convex_dir.mkdir()
        schema_file = convex_dir / "schema.ts"
        schema_file.write_text(
            """
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  tasks: defineTable({
    title: v.string(),
    status: v.string(),
  }).index("by_status", ["status"]),
});
"""
        )

        with patch("mc.cli._find_dashboard_dir", return_value=tmp_path):
            result = runner.invoke(mc_app, ["docs"])

        assert result.exit_code == 0
        assert "tasks" in result.output

    def test_docs_displays_functions(self, tmp_path):
        convex_dir = tmp_path / "convex"
        convex_dir.mkdir()
        # No schema file
        func_file = convex_dir / "tasks.ts"
        func_file.write_text(
            """
export const list = query({
  handler: async (ctx) => { return []; },
});

export const create = mutation({
  handler: async (ctx, args) => {},
});
"""
        )

        with patch("mc.cli._find_dashboard_dir", return_value=tmp_path):
            result = runner.invoke(mc_app, ["docs"])

        assert result.exit_code == 0
        assert "tasks" in result.output
        assert "list" in result.output
        assert "create" in result.output

    def test_docs_skips_internal_files(self, tmp_path):
        convex_dir = tmp_path / "convex"
        convex_dir.mkdir()
        internal = convex_dir / "_generated.ts"
        internal.write_text("export const stuff = query({});")
        public = convex_dir / "agents.ts"
        public.write_text("export const list = query({});")

        with patch("mc.cli._find_dashboard_dir", return_value=tmp_path):
            result = runner.invoke(mc_app, ["docs"])

        assert result.exit_code == 0
        assert "agents" in result.output
        # _generated should be skipped
        assert "_generated" not in result.output


# ── status help ─────────────────────────────────────────────────────


class TestStatusHelp:
    def test_status_in_help(self):
        result = runner.invoke(mc_app, ["--help"])
        assert result.exit_code == 0
        assert "status" in result.output

    def test_docs_in_help(self):
        result = runner.invoke(mc_app, ["--help"])
        assert result.exit_code == 0
        assert "docs" in result.output
