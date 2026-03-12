"""Completion reporting helpers extracted from the task executor."""

from __future__ import annotations

from pathlib import Path


def append_task_completion_heartbeat(
    *,
    title: str,
    task_id: str,
    agent_name: str,
    final_status: str,
    result: str | None,
) -> None:
    """Append a task completion update for the main agent to pick up."""
    from filelock import FileLock

    result_snippet = (result or "Task completed.").strip()
    if len(result_snippet) > 1000:
        result_snippet = result_snippet[:1000] + "\n...(truncated)..."

    heartbeat_content = (
        f"\n## Mission Control Update\n\n"
        f"The task **'{title}'** (ID: `{task_id}`) assigned to **{agent_name}** "
        f"has finished with status: `{final_status}`.\n\n"
        f"### Agent's Result:\n```\n{result_snippet}\n```\n\n"
        f"Please summarize this naturally and notify the user that the task is complete.\n"
    )

    heartbeat_file = Path.home() / ".nanobot" / "workspace" / "HEARTBEAT.md"
    lock = FileLock(str(heartbeat_file) + ".lock", timeout=10)
    with lock:
        with open(heartbeat_file, "a", encoding="utf-8") as f:
            f.write(heartbeat_content)
