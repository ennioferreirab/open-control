"""Plan tracker — parses plan files and tracks step completion."""
from __future__ import annotations

import fnmatch
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_config, get_project_root
from ..handler import BaseHandler


def is_plan_file(file_path: str) -> bool:
    """Check if a file path matches the plan pattern."""
    root = get_project_root()
    root_str = str(root)
    rel_path = file_path
    if file_path.startswith(root_str):
        rel_path = file_path[len(root_str):].lstrip("/")
    config = get_config()
    return fnmatch.fnmatch(rel_path, config.plan_pattern)


def parse_plan_tasks(content: str) -> list[dict]:
    """Parse task definitions from plan file content."""
    tasks: list[dict] = []
    current: dict | None = None

    for line in content.splitlines():
        m = re.match(r"^###\s+Task\s+(\d+):\s+(.+)", line)
        if m:
            if current is not None:
                tasks.append(current)
            current = {
                "id": int(m.group(1)),
                "name": m.group(2).strip(),
                "blocked_by": [],
            }
            continue

        if current is not None:
            b = re.match(r"^\*\*Blocked by:\*\*\s+(.+)", line.strip())
            if b:
                ids = [int(x) for x in re.findall(r"Task\s+(\d+)", b.group(1))]
                current["blocked_by"] = ids

    if current is not None:
        tasks.append(current)
    return tasks


def compute_parallel_groups(tasks: list[dict]) -> list[dict]:
    """Compute parallel execution groups for a list of tasks."""
    by_id = {t["id"]: t for t in tasks}
    all_ids = set(by_id.keys())
    group_of: dict[int, int] = {}
    remaining = set(all_ids)
    group_num = 1

    while remaining:
        ready = []
        for tid in sorted(remaining):
            blocked_by = [b for b in by_id[tid]["blocked_by"] if b in all_ids]
            if all(b not in remaining for b in blocked_by):
                ready.append(tid)
        if not ready:
            for tid in sorted(remaining):
                group_of[tid] = group_num
            break
        for tid in ready:
            group_of[tid] = group_num
            remaining.remove(tid)
        group_num += 1

    steps = []
    for i, t in enumerate(tasks):
        steps.append({
            "id": t["id"],
            "name": t["name"],
            "order": i + 1,
            "status": "pending",
            "blocked_by": t["blocked_by"],
            "parallel_group": group_of.get(t["id"], 1),
        })
    return steps


class PlanTrackerHandler(BaseHandler):
    events = [("PostToolUse", "Write"), ("TaskCompleted", None)]

    def handle(self) -> str | None:
        event = self.payload.get("hook_event_name", "")
        if event == "PostToolUse":
            return self._handle_write()
        elif event == "TaskCompleted":
            return self._handle_task_completed()
        return None

    def _handle_write(self) -> str | None:
        tool_input = self.payload.get("tool_input", {})
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None

        config = get_config()
        root = get_project_root()

        # Make path relative
        rel_path = file_path
        root_str = str(root)
        if file_path.startswith(root_str):
            rel_path = file_path[len(root_str):].lstrip("/")

        # Check glob match
        if not fnmatch.fnmatch(rel_path, config.plan_pattern):
            return None

        # Get content
        content = tool_input.get("content", "")
        if not content:
            abs_path = Path(file_path) if file_path.startswith("/") else root / file_path
            if not abs_path.exists():
                return None
            content = abs_path.read_text()

        # Parse tasks
        tasks = parse_plan_tasks(content)
        if not tasks:
            return None

        # Compute parallel groups
        steps = compute_parallel_groups(tasks)

        # Preserve completed statuses
        tracker_dir = root / config.tracker_dir
        tracker_dir.mkdir(parents=True, exist_ok=True)
        basename = Path(rel_path).stem
        tracker_path = tracker_dir / f"{basename}.json"

        if tracker_path.exists():
            try:
                old_data = json.loads(tracker_path.read_text())
                old_status = {s["id"]: s["status"] for s in old_data.get("steps", [])}
                for step in steps:
                    if old_status.get(step["id"]) == "completed":
                        step["status"] = "completed"
            except (json.JSONDecodeError, KeyError):
                pass

        # Write tracker
        tracker = {
            "plan_file": rel_path,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "steps": steps,
        }
        tracker_path.write_text(json.dumps(tracker, indent=2))

        # Update context
        self.ctx.active_plan = rel_path

        # Build summary
        return self._build_summary(steps)

    def _handle_task_completed(self) -> str | None:
        # Extract subject — handle both payload formats
        subject = (
            self.payload.get("task_subject", "")
            or self.payload.get("task", {}).get("subject", "")
        )
        if not subject:
            return None

        # Try numeric ID
        m = re.search(r"Task\s+(\d+)", subject)
        task_id = int(m.group(1)) if m else None

        config = get_config()
        root = get_project_root()
        tracker_dir = root / config.tracker_dir

        if not tracker_dir.is_dir():
            return None

        # Scan tracker files
        for tracker_path in sorted(tracker_dir.glob("*.json")):
            try:
                data = json.loads(tracker_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            matched_step = None
            for step in data.get("steps", []):
                if task_id is not None and step["id"] == task_id:
                    matched_step = step
                    break
                elif task_id is None and step["name"].lower() in subject.lower():
                    matched_step = step
                    break

            if matched_step is None or matched_step["status"] == "completed":
                continue

            # Mark completed
            matched_step["status"] = "completed"
            tracker_path.write_text(json.dumps(data, indent=2))

            # Calculate progress and unblocked
            done_ids = {s["id"] for s in data["steps"] if s["status"] == "completed"}
            total = len(data["steps"])
            done_count = len(done_ids)

            unblocked = []
            for s in data["steps"]:
                if (
                    s["status"] == "pending"
                    and s["blocked_by"]
                    and all(b in done_ids for b in s["blocked_by"])
                ):
                    unblocked.append(f"Task {s['id']}")

            msg = f"Step {matched_step['id']} '{matched_step['name']}' completed. Progress: {done_count}/{total} done."
            if unblocked:
                msg += f" Now unblocked: {', '.join(unblocked)}"
            return msg

        return None

    @staticmethod
    def _build_summary(steps: list[dict]) -> str:
        total = len(steps)
        step_by_id = {s["id"]: s for s in steps}
        groups: dict[int, list[int]] = defaultdict(list)
        for s in steps:
            groups[s["parallel_group"]].append(s["id"])

        descs = []
        for g in sorted(groups.keys()):
            ids = groups[g]
            if len(ids) > 1:
                descs.append("[" + ",".join(str(i) for i in ids) + "] can run parallel")
            else:
                step = step_by_id[ids[0]]
                if step["blocked_by"]:
                    descs.append(
                        f"[{ids[0]}] blocked by "
                        + ",".join(str(b) for b in step["blocked_by"])
                    )
                else:
                    descs.append(f"[{ids[0]}]")

        return f"Plan tracker created: {total} tasks. Parallel groups: {'; '.join(descs)}"
