"""Unit tests for CLI task commands (Story 2.7)."""

import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mc.cli import _get_bridge, _get_status_color, mc_app

runner = CliRunner()


# ── _get_status_color tests ──────────────────────────────────────────


class TestGetStatusColor:
    def test_inbox(self):
        assert _get_status_color("inbox") == "magenta"

    def test_assigned(self):
        assert _get_status_color("assigned") == "blue"

    def test_in_progress(self):
        assert _get_status_color("in_progress") == "cyan"

    def test_review(self):
        assert _get_status_color("review") == "yellow"

    def test_done(self):
        assert _get_status_color("done") == "green"

    def test_retrying(self):
        assert _get_status_color("retrying") == "yellow"

    def test_crashed(self):
        assert _get_status_color("crashed") == "red"

    def test_unknown_status(self):
        assert _get_status_color("something_else") == "white"


# ── _get_bridge tests ────────────────────────────────────────────────


class TestGetBridge:
    @patch("mc.cli.ConvexBridge" if False else "mc.bridge.ConvexClient")
    def test_get_bridge_from_env(self, MockClient):
        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            bridge = _get_bridge()
            MockClient.assert_called_once_with("https://test.convex.cloud")
            bridge.close()

    @patch("mc.bridge.ConvexClient")
    def test_get_bridge_with_admin_key(self, MockClient):
        mock_client = MockClient.return_value
        with patch.dict(
            os.environ,
            {"CONVEX_URL": "https://test.convex.cloud", "CONVEX_ADMIN_KEY": "secret"},
        ):
            bridge = _get_bridge()
            mock_client.set_admin_auth.assert_called_once_with("secret")
            bridge.close()

    def test_get_bridge_no_url_exits(self):
        from click.exceptions import Exit

        with patch.dict(os.environ, {}, clear=True):
            with patch("mc.cli._find_dashboard_dir") as mock_find:
                from pathlib import Path

                mock_find.return_value = Path("/nonexistent/dashboard")
                with pytest.raises(Exit):
                    _get_bridge()

    @patch("mc.bridge.ConvexClient")
    def test_get_bridge_from_env_local(self, MockClient, tmp_path):
        env_file = tmp_path / ".env.local"
        env_file.write_text('NEXT_PUBLIC_CONVEX_URL="https://from-env-local.convex.cloud"\n')

        with patch.dict(os.environ, {}, clear=True):
            with patch("mc.cli._find_dashboard_dir", return_value=tmp_path):
                bridge = _get_bridge()
                MockClient.assert_called_once_with("https://from-env-local.convex.cloud")
                bridge.close()


# ── tasks create tests ───────────────────────────────────────────────


class TestTasksCreate:
    @patch("mc.bridge.ConvexClient")
    def test_create_with_title(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = {"_id": "abc123"}

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "create", "Research AI trends"])

        assert result.exit_code == 0
        assert "Task created:" in result.output
        assert "Research AI trends" in result.output
        mock_client.mutation.assert_called_once()
        call_args = mock_client.mutation.call_args[0]
        assert call_args[0] == "tasks:create"
        assert call_args[1]["title"] == "Research AI trends"

    @patch("mc.bridge.ConvexClient")
    def test_create_with_description_and_tags(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = {"_id": "abc123"}

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(
                mc_app,
                [
                    "tasks",
                    "create",
                    "Test task",
                    "-d",
                    "A test description",
                    "-t",
                    "tag1,tag2,tag3",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_client.mutation.call_args[0]
        assert call_args[1]["title"] == "Test task"
        assert call_args[1]["description"] == "A test description"
        assert call_args[1]["tags"] == ["tag1", "tag2", "tag3"]

    @patch("mc.bridge.ConvexClient")
    def test_create_tags_trimmed(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(
                mc_app,
                ["tasks", "create", "Test", "-t", " tag1 , tag2 , "],
            )

        assert result.exit_code == 0
        call_args = mock_client.mutation.call_args[0]
        assert call_args[1]["tags"] == ["tag1", "tag2"]

    @patch("mc.bridge.ConvexClient")
    def test_create_without_title_prompts(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "create"], input="Prompted title\n")

        assert result.exit_code == 0
        assert "Task created:" in result.output
        call_args = mock_client.mutation.call_args[0]
        assert call_args[1]["title"] == "Prompted title"

    @patch("mc.bridge.ConvexClient")
    def test_create_closes_bridge(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            runner.invoke(mc_app, ["tasks", "create", "Test"])

        mock_client.close.assert_called_once()

    @patch("mc.bridge.ConvexClient")
    def test_create_closes_bridge_on_error(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.side_effect = Exception("Connection failed")

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            with patch("mc.bridge.time.sleep"):
                runner.invoke(mc_app, ["tasks", "create", "Test"])

        mock_client.close.assert_called_once()

    @patch("mc.bridge.ConvexClient")
    def test_create_no_description_omits_key(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.mutation.return_value = None

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            runner.invoke(mc_app, ["tasks", "create", "Test"])

        call_args = mock_client.mutation.call_args[0]
        assert "description" not in call_args[1]
        assert "tags" not in call_args[1]


# ── tasks list tests ─────────────────────────────────────────────────


class TestTasksList:
    @patch("mc.bridge.ConvexClient")
    def test_list_no_tasks(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "list"])

        assert result.exit_code == 0
        assert "No tasks found." in result.output

    @patch("mc.bridge.ConvexClient")
    def test_list_none_result(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = None

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "list"])

        assert result.exit_code == 0
        assert "No tasks found." in result.output

    @patch("mc.bridge.ConvexClient")
    def test_list_displays_tasks(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = [
            {
                "_id": "abc",
                "title": "Research AI",
                "status": "inbox",
                "assignedAgent": None,
                "createdAt": "2026-02-23T10:00:00Z",
            },
            {
                "_id": "def",
                "title": "Build API",
                "status": "in_progress",
                "assignedAgent": "dev-agent",
                "createdAt": "2026-02-22T08:00:00Z",
            },
        ]

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "list"])

        assert result.exit_code == 0
        assert "Tasks" in result.output
        assert "Research AI" in result.output
        assert "Build API" in result.output
        assert "dev-agent" in result.output

    @patch("mc.bridge.ConvexClient")
    def test_list_sorted_by_status(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = [
            {"_id": "1", "title": "Done task", "status": "done", "createdAt": "2026-01-01"},
            {"_id": "2", "title": "Inbox task", "status": "inbox", "createdAt": "2026-01-02"},
            {
                "_id": "3",
                "title": "In progress task",
                "status": "in_progress",
                "createdAt": "2026-01-03",
            },
        ]

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "list"])

        assert result.exit_code == 0
        # Inbox should appear before in_progress which should appear before done
        inbox_pos = result.output.find("Inbox task")
        ip_pos = result.output.find("In progress task")
        done_pos = result.output.find("Done task")
        assert inbox_pos < ip_pos < done_pos

    @patch("mc.bridge.ConvexClient")
    def test_list_truncates_long_title(self, MockClient):
        mock_client = MockClient.return_value
        long_title = "A" * 60
        mock_client.query.return_value = [
            {"_id": "1", "title": long_title, "status": "inbox", "createdAt": "2026-01-01"},
        ]

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "list"])

        assert result.exit_code == 0
        # Rich truncates with ellipsis character, and our code truncates with "..."
        assert long_title not in result.output

    @patch("mc.bridge.ConvexClient")
    def test_list_closes_bridge(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = []

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            runner.invoke(mc_app, ["tasks", "list"])

        mock_client.close.assert_called_once()

    @patch("mc.bridge.ConvexClient")
    def test_list_missing_fields_handled(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.query.return_value = [
            {"_id": "1", "status": "inbox"},
        ]

        with patch.dict(os.environ, {"CONVEX_URL": "https://test.convex.cloud"}):
            result = runner.invoke(mc_app, ["tasks", "list"])

        assert result.exit_code == 0
        assert "Untitled" in result.output


# ── tasks --help test ────────────────────────────────────────────────


class TestTasksHelp:
    def test_tasks_help(self):
        result = runner.invoke(mc_app, ["tasks", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "Manage Mission Control tasks" in result.output

    def test_tasks_no_args_shows_help(self):
        result = runner.invoke(mc_app, ["tasks"])
        # no_args_is_help=True causes exit code 0 for --help but 2 for bare invocation
        assert "create" in result.output
        assert "list" in result.output
