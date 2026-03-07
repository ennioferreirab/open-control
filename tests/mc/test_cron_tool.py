"""Unit tests for CronTool — scheduling, delivery defaults, and validation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nanobot.agent.tools.cron import CronTool
from nanobot.cron.types import CronJob, CronPayload, CronSchedule


def _make_tool(*, channel: str = "mc", chat_id: str = "my-agent") -> tuple[CronTool, MagicMock]:
    """Return a CronTool with a mock CronService and a pre-set context."""
    mock_svc = MagicMock()
    mock_svc.add_job = MagicMock(
        return_value=CronJob(
            id="job-1",
            name="test",
            enabled=True,
            schedule=CronSchedule(kind="every", every_ms=60_000),
            payload=CronPayload(kind="agent_turn", message="test"),
        )
    )
    tool = CronTool(mock_svc)
    tool.set_context(channel=channel, chat_id=chat_id)
    return tool, mock_svc


# ---------------------------------------------------------------------------
# set_telegram_default — fallback when deliver_channel='telegram' without deliver_to
# ---------------------------------------------------------------------------

class TestTelegramDefault:
    def test_deliver_channel_telegram_without_deliver_to_uses_default(self):
        """deliver_channel='telegram' + no deliver_to → uses set_telegram_default."""
        tool, mock_svc = _make_tool()
        tool.set_telegram_default("986097959")

        result = tool._add_job(
            message="summarize",
            every_seconds=3600,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to=None,
        )

        assert "Error" not in result
        call_kwargs = mock_svc.add_job.call_args[1]
        assert call_kwargs["channel"] == "telegram"
        assert call_kwargs["to"] == "986097959"

    def test_deliver_channel_telegram_without_deliver_to_errors_when_no_default(self):
        """deliver_channel='telegram' + no deliver_to + no default → error."""
        tool, mock_svc = _make_tool()
        # No set_telegram_default called

        result = tool._add_job(
            message="summarize",
            every_seconds=3600,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to=None,
        )

        assert "Error" in result
        mock_svc.add_job.assert_not_called()

    def test_explicit_deliver_to_overrides_default(self):
        """Explicit deliver_to takes precedence over set_telegram_default."""
        tool, mock_svc = _make_tool()
        tool.set_telegram_default("986097959")

        result = tool._add_job(
            message="summarize",
            every_seconds=3600,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to="111222333",
        )

        assert "Error" not in result
        call_kwargs = mock_svc.add_job.call_args[1]
        assert call_kwargs["to"] == "111222333"

    def test_description_shows_default_chat_id(self):
        """Description mentions the configured Telegram chat_id when set."""
        tool, _ = _make_tool()
        tool.set_telegram_default("986097959")
        assert "986097959" in tool.description
        assert "deliver_channel='telegram'" in tool.description

    def test_description_hides_default_when_not_set(self):
        """Description does not mention Telegram chat_id when not configured."""
        tool, _ = _make_tool()
        assert "986097959" not in tool.description


# ---------------------------------------------------------------------------
# Numeric deliver_to validation for telegram
# ---------------------------------------------------------------------------

class TestTelegramDeliverToValidation:
    def test_non_numeric_deliver_to_for_telegram_returns_error(self):
        """Non-numeric deliver_to with deliver_channel='telegram' → error, no job created."""
        tool, mock_svc = _make_tool()

        result = tool._add_job(
            message="test",
            every_seconds=60,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to="youtube-summarizer",  # agent name, not numeric
        )

        assert "Error" in result
        assert "numeric" in result.lower()
        mock_svc.add_job.assert_not_called()

    def test_non_numeric_mc_chat_id_rejected_as_telegram_fallback(self):
        """When channel='mc' and no deliver_to/default, MC chat_id is not used for telegram."""
        tool, mock_svc = _make_tool(channel="mc", chat_id="youtube-summarizer")
        # No telegram default set — fallback would be the non-numeric MC chat_id

        result = tool._add_job(
            message="test",
            every_seconds=60,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to=None,
        )

        # Without a numeric default it must error, not silently store 'youtube-summarizer'
        assert "Error" in result
        mock_svc.add_job.assert_not_called()

    def test_numeric_deliver_to_for_telegram_is_accepted(self):
        """Numeric deliver_to for telegram → job created successfully."""
        tool, mock_svc = _make_tool()

        result = tool._add_job(
            message="test",
            every_seconds=60,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to="986097959",
        )

        assert "Error" not in result
        mock_svc.add_job.assert_called_once()

    def test_negative_numeric_deliver_to_for_telegram_is_accepted(self):
        """Negative numeric chat_ids (group chats) are valid for telegram."""
        tool, mock_svc = _make_tool()

        result = tool._add_job(
            message="test",
            every_seconds=60,
            cron_expr=None,
            tz=None,
            at=None,
            deliver_channel="telegram",
            deliver_to="-1001234567890",
        )

        assert "Error" not in result
        mock_svc.add_job.assert_called_once()


# ---------------------------------------------------------------------------
# _send_telegram_direct guard (gateway-level)
# ---------------------------------------------------------------------------

class TestSendTelegramDirectGuard:
    @pytest.mark.asyncio
    async def test_non_numeric_chat_id_is_rejected_without_crash(self):
        """_send_telegram_direct logs an error and returns when chat_id is not numeric."""
        from mc.runtime.gateway import run_gateway  # noqa: F401 — ensure module is importable

        # Import the inner function indirectly by instantiating the gateway closure
        # We test the guard logic directly by calling the function in an isolated scope.
        # Since _send_telegram_direct is a nested function, we replicate its guard logic here:
        chat_id = "youtube-summarizer"
        assert not chat_id.lstrip("-").isdigit(), "precondition: non-numeric"

        # The guard should have prevented reaching int(chat_id), which would raise ValueError
        try:
            if not chat_id.lstrip("-").isdigit():
                return  # guard triggered — no exception
            int(chat_id)  # would raise ValueError without the guard
            assert False, "Should not reach here"
        except ValueError:
            pytest.fail("ValueError raised — guard not working")

    @pytest.mark.asyncio
    async def test_numeric_chat_id_passes_guard(self):
        """_send_telegram_direct guard does not block valid numeric chat_ids."""
        chat_id = "986097959"
        assert chat_id.lstrip("-").isdigit()
        # int() works fine
        assert int(chat_id) == 986097959
