"""Unit tests for the cron IPC handler in MCSocketServer."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from claude_code.ipc_server import MCSocketServer

pytestmark = pytest.mark.asyncio


def _make_mock_cron_service(jobs=None):
    """Create a mock CronService that returns controllable results."""
    mock = MagicMock()
    mock.list_jobs.return_value = jobs or []

    def add_job(**kwargs):
        job = MagicMock()
        job.name = kwargs.get("name", "test")
        job.id = "mock-job-id"
        return job

    mock.add_job.side_effect = add_job
    mock.remove_job.return_value = True
    return mock


def _make_server(cron_service=None) -> MCSocketServer:
    """Create an MCSocketServer with no bridge/bus and optional cron_service."""
    return MCSocketServer(bridge=None, bus=None, cron_service=cron_service)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCronHandlerList:
    async def test_list_empty(self):
        """When no jobs exist, returns 'No scheduled jobs'."""
        svc = _make_mock_cron_service(jobs=[])
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(action="list")

        assert "No scheduled jobs" in result["result"]

    async def test_list_with_jobs(self):
        """When jobs exist, their names appear in the result."""
        mock_job = MagicMock()
        mock_job.name = "morning-standup"
        mock_job.id = "job001"
        mock_job.schedule = MagicMock()
        mock_job.schedule.kind = "cron"

        svc = _make_mock_cron_service(jobs=[mock_job])
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(action="list")

        assert "morning-standup" in result["result"]


class TestCronHandlerAdd:
    async def test_add_job_with_cron_expr(self):
        """add action with cron_expr creates job and returns confirmation."""
        svc = _make_mock_cron_service()
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(
            action="add",
            message="daily report",
            cron_expr="0 9 * * *",
            agent_name="agent",
        )

        assert "Created job" in result["result"]
        assert svc.add_job.called

    async def test_add_job_with_every_seconds(self):
        """add action with every_seconds creates a recurring job."""
        svc = _make_mock_cron_service()
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(
            action="add",
            message="ping every minute",
            every_seconds=60,
            agent_name="agent",
        )

        assert "Created job" in result["result"]
        assert svc.add_job.called

    async def test_add_missing_message(self):
        """add action without message returns an error."""
        svc = _make_mock_cron_service()
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(
            action="add",
            cron_expr="0 9 * * *",
            agent_name="agent",
        )

        assert "error" in result
        assert "message" in result["error"]


class TestCronHandlerRemove:
    async def test_remove_job(self):
        """remove action with valid job_id returns confirmation."""
        svc = _make_mock_cron_service()
        svc.remove_job.return_value = True
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(action="remove", job_id="abc123")

        assert "Removed" in result["result"]
        svc.remove_job.assert_called_once_with("abc123")

    async def test_remove_missing_job_id(self):
        """remove action without job_id returns an error."""
        svc = _make_mock_cron_service()
        server = _make_server(cron_service=svc)

        result = await server._handle_cron(action="remove")

        assert "error" in result
        assert "job_id" in result["error"]


class TestCronHandlerNoCronService:
    async def test_no_cron_service(self):
        """When cron_service is None, returns an error dict."""
        server = _make_server(cron_service=None)

        result = await server._handle_cron(action="list")

        assert "error" in result
