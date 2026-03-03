"""Cron tool for scheduling reminders and tasks."""

from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._task_id: str | None = None
        self._agent_name: str | None = None
        self._telegram_default_chat_id: str = ""

    def set_context(self, channel: str, chat_id: str, task_id: str | None = None, agent_name: str | None = None) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
        self._task_id = task_id
        self._agent_name = agent_name

    def set_telegram_default(self, chat_id: str) -> None:
        """Set the default Telegram chat_id for cron delivery (used when running in MC context)."""
        self._telegram_default_chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        base = (
            "Schedule reminders and recurring tasks. Actions: add, list, remove. "
            "Supports: cron_expr (recurring), every_seconds (interval), at (one-time). "
            "Use tz with cron_expr for IANA timezone (e.g. 'America/Vancouver')."
        )
        if self._channel:
            base += (
                f" Results are delivered to the current channel ({self._channel})."
                " Use deliver_channel and deliver_to to override delivery destination."
            )
        if self._telegram_default_chat_id:
            base += (
                f" To deliver to Telegram, set deliver_channel='telegram'"
                f" (deliver_to defaults to '{self._telegram_default_chat_id}')."
            )
        return base
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform"
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message (for add)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for scheduled tasks)"
                },
                "tz": {
                    "type": "string",
                    "description": "IANA timezone for cron expressions (e.g. 'America/Vancouver')"
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove)"
                },
                "deliver_channel": {
                    "type": "string",
                    "description": "Override delivery channel (e.g. 'telegram'). Defaults to current session channel."
                },
                "deliver_to": {
                    "type": "string",
                    "description": "Delivery recipient for the chosen channel. For 'telegram': a numeric chat ID (e.g. '986097959'). For 'mc': an agent name. Required if deliver_channel is set."
                }
            },
            "required": ["action"]
        }
    
    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        at: str | None = None,
        job_id: str | None = None,
        deliver_channel: str | None = None,
        deliver_to: str | None = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            return self._add_job(message, every_seconds, cron_expr, tz, at, deliver_channel, deliver_to)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"
    
    def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        cron_expr: str | None,
        tz: str | None,
        at: str | None,
        deliver_channel: str | None = None,
        deliver_to: str | None = None,
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        if deliver_channel and not deliver_to:
            # For telegram, fall back to the configured default chat_id if available
            if deliver_channel == "telegram" and self._telegram_default_chat_id:
                deliver_to = self._telegram_default_chat_id
            else:
                return "Error: deliver_to is required when deliver_channel is set"
        if deliver_to and not deliver_channel:
            return "Error: deliver_channel is required when deliver_to is set"
        if deliver_channel == "telegram":
            effective_to = deliver_to or self._chat_id
            if not effective_to.lstrip("-").isdigit():
                return (
                    f"Error: deliver_to must be a numeric Telegram chat ID "
                    f"(e.g. '986097959'), got '{effective_to}'. "
                    "Ask the user for their Telegram chat ID — it cannot be an agent name."
                )
        if tz and not cron_expr:
            return "Error: tz can only be used with cron_expr"
        if tz:
            from zoneinfo import ZoneInfo
            try:
                ZoneInfo(tz)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{tz}'"
        
        # Build schedule
        delete_after = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
        elif at:
            from datetime import datetime
            dt = datetime.fromisoformat(at)
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, cron_expr, or at is required"
        
        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=deliver_channel or self._channel,
            to=deliver_to or self._chat_id,
            delete_after_run=delete_after,
            task_id=self._task_id,
            agent=self._agent_name,
        )
        return f"Created job '{job.name}' (id: {job.id})"
    
    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
