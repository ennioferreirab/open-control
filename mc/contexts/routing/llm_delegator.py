"""LLM-powered delegation router — selects the best agent via LLM reasoning.

Path A: User selected an agent → direct assignment (reason_code="explicit_assignment").
Path B: Auto (no agent) → LLM picks the single best agent from the active registry.

No silent fallbacks: LLM failure → explicit task failure.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mc.contexts.routing.router import DirectDelegationRouter, RoutingDecision

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 30
DESCRIPTION_TRUNCATE = 2000

SYSTEM_PROMPT = """\
You are an agent routing assistant. Select the single best agent for this task \
based on skills, role, availability, and workload.

You MUST respond with valid JSON only, no markdown, no explanation.

## Response Format

{
  "target_agent": "agent-name",
  "reasoning": "Brief explanation of why this agent is the best fit",
  "confidence": "high|medium|low"
}

## Rules

- target_agent must be one of the agent names listed in the user message
- NEVER select "orchestrator-agent" — it only plans, it never executes
- Pick the agent whose skills and role best match the task
- When skills are equal, prefer the agent with lower workload (fewer tasks executed)
- confidence should reflect how well the agent's capabilities match the task"""

USER_PROMPT_TEMPLATE = """\
Task: {title}
Description: {description}

Available agents:
{agent_roster}

Select the single best agent for this task."""


class LLMDelegationRouter:
    """Routes tasks to agents via explicit assignment or LLM selection.

    Path A — ``assignedAgent`` present: delegates to ``DirectDelegationRouter``.
    Path B — no agent (Auto): calls LLM to pick the best agent from registry.
    """

    def __init__(self, bridge: ConvexBridge) -> None:
        self._bridge = bridge

    async def route(self, task_data: dict[str, Any]) -> RoutingDecision:
        """Route a task to the best agent.

        Returns:
            RoutingDecision on success.

        Raises:
            RuntimeError: On any failure (LLM timeout, invalid response,
                agent not found, empty registry). No silent fallbacks.
        """
        assigned = task_data.get("assigned_agent")
        if assigned:
            return self._route_explicit(task_data, assigned)
        return await self._route_llm(task_data)

    def _route_explicit(self, task_data: dict[str, Any], assigned: str) -> RoutingDecision:
        """Path A: User selected an agent — delegate to DirectDelegationRouter."""
        router = DirectDelegationRouter(self._bridge)
        decision = router.route(task_data)
        if decision is None:
            raise RuntimeError(
                f"Explicitly assigned agent '{assigned}' not found in active registry"
            )
        return decision

    async def _route_llm(self, task_data: dict[str, Any]) -> RoutingDecision:
        """Path B: No agent selected — LLM picks the best one."""
        from datetime import UTC, datetime

        registry = self._bridge.list_active_registry_view()
        if not registry:
            raise RuntimeError("No active agents in registry — cannot delegate task")

        candidates = list(registry)

        # Board scoping
        board_id = task_data.get("board_id")
        if board_id:
            try:
                board = self._bridge.get_board_by_id(board_id)
                if board:
                    enabled = board.get("enabled_agents") or []
                    if enabled:
                        candidates = [a for a in candidates if a.get("name") in enabled]
            except Exception:
                logger.warning(
                    "[llm_delegator] Failed to fetch board for filtering",
                    exc_info=True,
                )

        if not candidates:
            raise RuntimeError("No delegatable agents after board filtering")

        # Filter out crashed agents
        candidates = [a for a in candidates if a.get("status") != "crashed"]
        if not candidates:
            raise RuntimeError("All candidate agents are in crashed state")

        agent_roster = self._format_agent_roster(candidates)

        title = task_data.get("title", "Untitled")
        description = (task_data.get("description") or "")[:DESCRIPTION_TRUNCATE]

        user_prompt = USER_PROMPT_TEMPLATE.format(
            title=title,
            description=description or "No description provided",
            agent_roster=agent_roster,
        )

        full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

        from mc.infrastructure.acp.utility import extract_json, run_utility_turn

        try:
            text = await run_utility_turn(full_prompt, tier="low", timeout_s=LLM_TIMEOUT_SECONDS)
            parsed = extract_json(text)
        except Exception as exc:
            raise RuntimeError(f"LLM delegation failed: {exc}") from exc

        target_agent = parsed.get("target_agent")
        reasoning = parsed.get("reasoning", "")
        confidence = parsed.get("confidence", "unknown")

        if not target_agent or not isinstance(target_agent, str):
            raise RuntimeError(f"LLM delegation response missing 'target_agent': {parsed}")

        # Validate target_agent exists in candidates
        candidate_names = {a.get("name") for a in candidates}
        if target_agent not in candidate_names:
            raise RuntimeError(
                f"LLM selected agent '{target_agent}' not found in active registry. "
                f"Available: {sorted(n for n in candidate_names if n is not None)}"
            )

        registry_snapshot = [{"name": a.get("name"), "role": a.get("role")} for a in registry]

        return RoutingDecision(
            target_agent=target_agent,
            reason=f"LLM delegation ({confidence}): {reasoning}",
            reason_code="llm_delegation",
            registry_snapshot=registry_snapshot,
            routed_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _format_agent_roster(agents: list[dict[str, Any]]) -> str:
        """Format agent registry for the LLM prompt."""
        lines = []
        for agent in agents:
            name = agent.get("name", "unknown")
            role = agent.get("role", "agent")
            skills = agent.get("skills") or []
            tasks_executed = agent.get("tasksExecuted", 0)
            status = agent.get("status", "idle")
            skills_str = ", ".join(skills) if skills else "general"
            lines.append(
                f"- {name} (role: {role}, skills: [{skills_str}], "
                f"tasks_executed: {tasks_executed}, status: {status})"
            )
        return "\n".join(lines)
