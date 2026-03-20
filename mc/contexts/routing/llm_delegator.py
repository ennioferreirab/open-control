"""LLM-powered delegation router — selects the best agent via LLM reasoning.

Path A: User selected an agent → direct assignment (reason_code="explicit_assignment").
Path B: Auto (no agent) → LLM picks the single best agent from the active registry.

No silent fallbacks: LLM failure → explicit task failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from mc.contexts.routing.router import DirectDelegationRouter, RoutingDecision
from mc.infrastructure.providers.factory import create_provider

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 30
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 256
DESCRIPTION_TRUNCATE = 2000
PREFERRED_TIER = "tier:standard-low"

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
- NEVER select "lead-agent" — it only plans, it never executes
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

        # Resolve model: prefer tier:standard-low, fall back to lead-agent model
        model = await self._resolve_model()

        # Call LLM
        try:
            provider, resolved_model = create_provider(model=model)
        except Exception as exc:
            raise RuntimeError(f"Failed to create LLM provider for delegation: {exc}") from exc

        try:
            response = await asyncio.wait_for(
                provider.chat(
                    model=resolved_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise RuntimeError(f"LLM delegation timed out after {LLM_TIMEOUT_SECONDS}s") from exc
        except Exception as exc:
            raise RuntimeError(f"LLM delegation call failed: {exc}") from exc

        if response.finish_reason == "error":
            raise RuntimeError(f"LLM delegation returned error: {response.content or 'unknown'}")

        content = (response.content or "").strip()
        if not content:
            raise RuntimeError("LLM delegation returned empty response")

        # Parse JSON response
        try:
            # Strip markdown fences if present
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [line for line in lines if not line.startswith("```")]
                content = "\n".join(lines)
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"LLM delegation returned invalid JSON: {exc}\nResponse: {content[:500]}"
            ) from exc

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

    async def _resolve_model(self) -> str | None:
        """Resolve the model to use for delegation LLM call.

        Prefers tier:standard-low. Falls back to the lead-agent's configured model.
        Returns None if neither is available (factory will use config default).
        """
        from mc.infrastructure.providers.tier_resolver import TierResolver
        from mc.types import LEAD_AGENT_NAME

        # Try tier:standard-low first
        try:
            resolver = TierResolver(self._bridge)
            resolved = resolver.resolve_model(PREFERRED_TIER)
            if resolved:
                return resolved
        except (ValueError, Exception):
            logger.debug(
                "[llm_delegator] tier:standard-low not configured, trying lead-agent model"
            )

        # Fall back to lead-agent model
        try:
            agent_data = await asyncio.to_thread(self._bridge.get_agent_by_name, LEAD_AGENT_NAME)
            if agent_data:
                lead_model = agent_data.get("model")
                if lead_model:
                    return lead_model
        except Exception:
            logger.debug("[llm_delegator] Failed to fetch lead-agent model", exc_info=True)

        return None

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
