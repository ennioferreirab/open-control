import json

import pytest

from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule


def test_add_job_rejects_unknown_timezone(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")

    with pytest.raises(ValueError, match="unknown timezone 'America/Vancovuer'"):
        service.add_job(
            name="tz typo",
            schedule=CronSchedule(kind="cron", expr="0 9 * * *", tz="America/Vancovuer"),
            message="hello",
        )

    assert service.list_jobs(include_disabled=True) == []


def test_add_job_accepts_valid_timezone(tmp_path) -> None:
    service = CronService(tmp_path / "cron" / "jobs.json")

    job = service.add_job(
        name="tz ok",
        schedule=CronSchedule(kind="cron", expr="0 9 * * *", tz="America/Vancouver"),
        message="hello",
    )

    assert job.schedule.tz == "America/Vancouver"
    assert job.state.next_run_at_ms is not None


def test_add_job_with_agent_roundtrips(tmp_path) -> None:
    """A job created with agent= is persisted to disk and reloaded correctly."""
    store_path = tmp_path / "cron" / "jobs.json"
    service = CronService(store_path)

    service.add_job(
        name="yt summarizer",
        schedule=CronSchedule(kind="cron", expr="0 8 * * *"),
        message="Summarize YouTube channels",
        agent="youtube-summarizer",
    )

    # Create a fresh service pointing to the same file to force a reload from disk
    service2 = CronService(store_path)
    jobs = service2.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].payload.agent == "youtube-summarizer"


def test_parse_old_job_without_agent_defaults_none(tmp_path) -> None:
    """An old-format job in jobs.json without an 'agent' key loads with agent=None."""
    store_path = tmp_path / "cron" / "jobs.json"
    store_path.parent.mkdir(parents=True, exist_ok=True)

    old_format = {
        "version": 1,
        "jobs": [
            {
                "id": "abc12345",
                "name": "old job",
                "enabled": True,
                "schedule": {"kind": "cron", "expr": "0 9 * * *", "tz": None, "atMs": None, "everyMs": None},
                "payload": {
                    "kind": "agent_turn",
                    "message": "do something",
                    "deliver": False,
                    "channel": None,
                    "to": None,
                    "taskId": None,
                    # intentionally missing "agent" key
                },
                "state": {"nextRunAtMs": None, "lastRunAtMs": None, "lastStatus": None, "lastError": None},
                "createdAtMs": 0,
                "updatedAtMs": 0,
                "deleteAfterRun": False,
            }
        ],
    }
    store_path.write_text(json.dumps(old_format), encoding="utf-8")

    service = CronService(store_path)
    jobs = service.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].payload.agent is None
