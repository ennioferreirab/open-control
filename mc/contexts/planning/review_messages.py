"""Helpers for rendering plan review requests into the task thread."""

from __future__ import annotations

from mc.types import ExecutionPlan


def build_plan_review_message(plan: ExecutionPlan) -> str:
    """Return a compact markdown summary for a plan review request."""
    lines = ["## Execution Plan", ""]

    for index, step in enumerate(sorted(plan.steps, key=lambda item: item.order), start=1):
        title = step.title or step.description or step.temp_id
        lines.append(f"{index}. **{title}**")
        lines.append(f"   - Agent: `{step.assigned_agent}`")
        lines.append(f"   - {step.description}")
        if step.blocked_by:
            blockers = ", ".join(f"`{dep}`" for dep in step.blocked_by)
            lines.append(f"   - Depends on: {blockers}")

    lines.extend(
        [
            "",
            "Approve to kick off, reject with feedback, or reply below with requested changes.",
        ]
    )
    return "\n".join(lines)


def build_plan_review_metadata(plan: ExecutionPlan) -> dict[str, str]:
    """Return thread metadata for the current plan version."""
    return {
        "kind": "request",
        "plan_generated_at": plan.generated_at,
    }
