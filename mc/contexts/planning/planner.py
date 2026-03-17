"""LLM-based task planner for intelligent agent routing.

Decomposes tasks into structured execution plans using LLM reasoning
instead of keyword-matching heuristics. Falls back to heuristic planning
on LLM failure.

Created for Story 4.5 — extracted from orchestrator.py per NFR21
(500-line module limit).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mc.bridge import ConvexBridge

from mc.contexts.planning.parser import (  # noqa: F401
    STANDARD_TOOLS,
    _build_agent_roster,
    _build_file_summary,
    _build_task_shape_hints,
    _is_delegatable,
    _load_lead_agent_planning_skills,
    _parse_plan_response,
    extract_keywords,
    score_agent,
)
from mc.types import (
    HUMAN_AGENT_NAME,
    LEAD_AGENT_NAME,
    NANOBOT_AGENT_NAME,
    AgentData,
    ExecutionPlan,
    ExecutionPlanStep,
    extract_cc_model_name,
    is_cc_model,
    is_lead_agent,
)

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 90
DEFAULT_PLANNING_REASONING_LEVEL = "low"
CC_PLANNING_MAX_TURNS = 6

SYSTEM_PROMPT = """\
You are a task planning assistant for a multi-agent system. Decompose tasks into \
structured execution steps and assign each step to the most appropriate agent.

You MUST respond with valid JSON only, no markdown, no explanation.

## Decomposition Guidelines

- Each step = 1 clear objective. Never mix unrelated actions in one step.
- Analyze the task complexity and decompose accordingly:
  - **Simple tasks** (single lookup, quick edit, direct question): 1 step is fine.
  - **Moderate tasks** (research + synthesize, build + test): 2-3 steps with clear phases.
  - **Complex tasks** (multi-source research, create + iterate, plan + execute): 3-5 steps.
- When the user asks for multiple independent items (for example: 3 files, 5 videos, 10 URLs),
  prefer one item-level step per item or chunk so those steps can run in parallel.
- For batch requests, add a final synthesis/aggregation step that depends on all item-level steps.
- If the same specialist agent can execute multiple independent item-level steps, still split them
  into separate steps so the dispatcher can run them concurrently.
- Each step description must be thorough and self-contained — it is the ONLY instruction \
the executor agent will receive. Include: what to do, how to approach it, what sources \
to check, and what output to produce.
- When downstream synthesis depends on step outputs, explicitly instruct each upstream step to
  save a distinct output artifact that the final step can combine.
- Keep plans compact. Prefer 1-6 steps.
- You may exceed 6 steps only when the user explicitly asked for many independent items and
  preserving correct parallelization is more important than staying under the preferred limit.

## Tool Awareness

Executor agents have tools: file I/O, shell exec, web search, cron scheduling.
- Assign a step to the agent that HAS the right skill for the tool needed.
- Do NOT create a separate "delegation" or "coordination" step — the agent executes directly.

## Anti-Patterns (never do these)

- Mixing "do X" and "schedule Y" in one step when they are unrelated concerns
- Creating "coordination", "handoff", or "review" steps — agents work autonomously
- Creating a single vague step that just restates the task title
- Writing step descriptions that are too brief for the agent to act on

## Examples

Example 1 — Simple task (1 step):
Task: "Summarize the Q3 report"
Good plan: 1 step assigned to the research agent. Description explains what to summarize \
and the expected output format.

Example 2 — Research + creation task (3 steps):
Task: "Research competitor pricing and create a comparison document"
Good plan: step_1 researches competitor A pricing (web agent), step_2 researches competitor B \
pricing (web agent, parallel with step_1), step_3 creates comparison document (docs agent, \
blocked by step_1 and step_2).

Example 3 — Action + scheduling (2 steps, same agent):
Task: "Fetch weather data and schedule a daily refresh"
Good plan: step_1 fetches data (agent with web_search), step_2 sets up cron \
(same agent, blocked by step_1).

Example 4 — Multi-phase content creation (3 steps):
Task: "Create a marketing plan for AI product launch based on YouTube and blog references"
Good plan: step_1 researches YouTube creator references and copy patterns (web agent), \
step_2 researches blog references and launch copy examples (web agent, parallel with step_1), \
step_3 synthesizes findings into a structured marketing plan (docs agent, blocked by step_1 and step_2).

Example 5 — Batch media request (6 steps):
Task: "Transcribe and summarize the latest 5 videos from this YouTube channel"
Good plan: step_1..step_5 each identify one of the 5 most recent videos and transcribe/summarize \
that specific video (all assigned to youtube-summarizer in the same parallel group), \
step_6 aggregates the five per-video outputs into a combined cross-video summary.

## Response Format

{
  "steps": [
    {
      "tempId": "step_1",
      "title": "Short action-oriented title",
      "description": "Detailed, self-contained instructions for the executor agent. Include: objective, approach, sources to check, and expected output.",
      "assignedAgent": "agent-name",
      "blockedBy": [],
      "parallelGroup": 1,
      "order": 1
    }
  ]
}

## Rules

- tempId must be "step_1", "step_2", etc.
- assignedAgent must be one of the agent names listed in the user message
- If no specialist agent matches, assign "nanobot" as fallback
- NEVER assign "lead-agent" to any step — lead-agent only plans, it never executes
- You may assign "human" to steps requiring manual review, approval, or human action. Human steps pause execution until a person accepts them.
- blockedBy is a list of tempIds that must complete before this step can start
- Steps with no blockers that can run simultaneously share the same parallelGroup number
- Steps that depend on others get a higher parallelGroup number
- order is display/execution order (1, 2, 3, ...)
- title should be brief and action-oriented
- description MUST be detailed enough for the agent to work autonomously — \
think of it as a complete task brief"""

USER_PROMPT_TEMPLATE = """\
Task: {title}
Description: {description}

Available agents (name, role, skills, tools):
{agent_roster}

Create an execution plan for this task. Decompose into as many steps as the task \
genuinely requires — use 1 step for simple tasks, 2-6 steps for complex ones, \
or more when the user explicitly requested many independent items. \
Write detailed step descriptions that the executor agent can act on autonomously."""


class TaskPlanner:
    """Plans task execution using LLM reasoning."""

    def __init__(self, bridge: "ConvexBridge | None" = None) -> None:
        self._bridge = bridge

    async def plan_task(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        explicit_agent: str | None = None,
        files: list[dict] | None = None,
        model: str | None = None,
        reasoning_level: str | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan for a task.

        If explicit_agent is set, all steps are assigned to that agent.
        On LLM failure, falls back to heuristic planning.
        """
        started_at = time.perf_counter()
        plan = await self._llm_plan(
            title,
            description,
            agents,
            files=files,
            model=model,
            reasoning_level=reasoning_level,
        )
        if explicit_agent:
            self._override_agents(plan, explicit_agent)
        self._validate_agent_names(plan, agents)
        self._prevent_lead_agent_steps(plan, agents)
        logger.info(
            "[planner] Planned task via LLM in %.2fs (%d steps)",
            time.perf_counter() - started_at,
            len(plan.steps),
        )
        return plan

    async def _llm_plan(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        files: list[dict] | None = None,
        model: str | None = None,
        reasoning_level: str | None = None,
    ) -> ExecutionPlan:
        """Call LLM to generate the plan."""
        from nanobot.config.loader import load_config

        from mc.infrastructure.providers.factory import create_provider

        agent_roster = _build_agent_roster(agents)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            title=title,
            description=description or "No description provided",
            agent_roster=agent_roster,
        )
        file_summary = _build_file_summary(files or [])
        if file_summary:
            user_prompt = user_prompt + "\n\n" + file_summary
        task_shape_hints = _build_task_shape_hints(title, description)
        if task_shape_hints:
            user_prompt = user_prompt + "\n\n" + task_shape_hints

        planning_skill_names, planning_skill_content = _load_lead_agent_planning_skills()
        planner_system_prompt = SYSTEM_PROMPT
        if planning_skill_content:
            planner_system_prompt += (
                "\n\n## Activated Lead-Agent Planning Skills\n\n"
                "The following skill instructions are active for this planning task.\n"
                "Apply them when they fit the request.\n\n"
                f"{planning_skill_content}"
            )
            logger.info(
                "[planner] Loaded lead-agent planning skills for prompt injection: %s",
                planning_skill_names,
            )

        selected_model = model or load_config().agents.defaults.model
        if is_cc_model(selected_model):
            return await self._cc_plan(
                user_prompt=user_prompt,
                model=selected_model,
                reasoning_level=reasoning_level or DEFAULT_PLANNING_REASONING_LEVEL,
                lead_agent_skills=planning_skill_names,
            )

        provider, resolved_model = create_provider(model=selected_model)
        response = await asyncio.wait_for(
            provider.chat(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": planner_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
                reasoning_level=reasoning_level,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

        if response.finish_reason == "error":
            raise RuntimeError(response.content or "LLM planning request failed")

        return _parse_plan_response(response.content)

    async def _cc_plan(
        self,
        *,
        user_prompt: str,
        model: str,
        reasoning_level: str | None = None,
        lead_agent_skills: list[str] | None = None,
    ) -> ExecutionPlan:
        """Generate a plan through the Claude Code backend for cc/ models."""
        if self._bridge is None:
            raise RuntimeError("CC planning requires a bridge-backed TaskPlanner")

        from claude_code.ipc_server import MCSocketServer
        from claude_code.provider import ClaudeCodeProvider
        from claude_code.types import ClaudeCodeOpts
        from claude_code.workspace import CCWorkspaceManager
        from nanobot.config.loader import load_config

        from mc.contexts.conversation.ask_user.handler import AskUserHandler
        from mc.infrastructure.orientation import load_orientation

        cc_opts = ClaudeCodeOpts()
        cc_opts.max_turns = CC_PLANNING_MAX_TURNS
        if reasoning_level:
            effort_map = {"low": "low", "medium": "medium", "high": "high", "max": "high"}
            cc_opts.effort_level = effort_map.get(reasoning_level, "high")
        else:
            cc_opts.effort_level = DEFAULT_PLANNING_REASONING_LEVEL

        agent_data = AgentData(
            name=LEAD_AGENT_NAME,
            display_name="Lead Agent",
            role="orchestrator",
            prompt=SYSTEM_PROMPT,
            model=extract_cc_model_name(model),
            backend="claude-code",
            skills=list(lead_agent_skills or []),
            claude_code_opts=cc_opts,
            is_system=True,
        )
        logger.info(
            "[planner] CC planning config: model=%s max_turns=%s effort=%s",
            model,
            cc_opts.max_turns,
            cc_opts.effort_level,
        )

        planning_task_id = f"planner-{uuid.uuid4().hex[:8]}"
        ws_mgr = CCWorkspaceManager()
        ws_ctx = ws_mgr.prepare(
            LEAD_AGENT_NAME,
            agent_data,
            planning_task_id,
            orientation=load_orientation(LEAD_AGENT_NAME),
            task_prompt=user_prompt,
        )

        ask_handler = AskUserHandler()
        ipc_server = MCSocketServer(self._bridge, None)
        ipc_server.set_ask_user_handler(ask_handler)
        await ipc_server.start(ws_ctx.socket_path)
        try:
            cfg = load_config()
            provider = ClaudeCodeProvider(
                cli_path=cfg.claude_code.cli_path,
                defaults=cfg.claude_code,
            )
            result = await provider.execute_task(
                prompt=user_prompt,
                agent_config=agent_data,
                task_id=planning_task_id,
                workspace_ctx=ws_ctx,
            )
            if result.is_error:
                raise RuntimeError(result.output or "Claude Code planning request failed")
            return _parse_plan_response(result.output)
        finally:
            await ipc_server.stop()

    def _validate_agent_names(self, plan: ExecutionPlan, agents: list[AgentData]) -> None:
        """Replace invalid/disallowed agent names with nanobot."""
        fallback_agent = self._fallback_agent_name(agents)
        delegatable_names = {a.name for a in agents if _is_delegatable(a)} | {
            NANOBOT_AGENT_NAME,
            HUMAN_AGENT_NAME,
        }
        for step in plan.steps:
            if not step.assigned_agent or step.assigned_agent not in delegatable_names:
                if step.assigned_agent:
                    logger.warning(
                        "[planner] Invalid/disallowed agent '%s' on step '%s', replacing with '%s'",
                        step.assigned_agent,
                        step.temp_id,
                        fallback_agent,
                    )
                step.assigned_agent = fallback_agent

    def _override_agents(self, plan: ExecutionPlan, agent_name: str) -> None:
        """Override all step assignments with an explicit agent."""
        assigned_name = NANOBOT_AGENT_NAME if is_lead_agent(agent_name) else agent_name
        if assigned_name != agent_name:
            logger.warning(
                "[planner] Explicit lead-agent override replaced with '%s' "
                "(pure orchestrator invariant)",
                assigned_name,
            )
        for step in plan.steps:
            step.assigned_agent = assigned_name

    def _fallback_agent_name(self, agents: list[AgentData]) -> str:
        """Choose a non-lead fallback agent name.

        Prefers the first delegatable agent over the hardcoded nanobot default
        so that agents with explicit backends (e.g., cc/) are not silently
        downgraded to the nanobot runner.
        """
        for a in agents:
            if _is_delegatable(a) and not is_lead_agent(a.name):
                return a.name
        return NANOBOT_AGENT_NAME

    def _prevent_lead_agent_steps(self, plan: ExecutionPlan, agents: list[AgentData]) -> None:
        """Final enforcement pass: lead-agent can never be a step executor."""
        fallback_agent = self._fallback_agent_name(agents)
        for step in plan.steps:
            if is_lead_agent(step.assigned_agent):
                logger.warning(
                    "[planner] Step '%s' assigned to lead-agent; replacing with "
                    "'%s' (pure orchestrator invariant)",
                    step.temp_id,
                    fallback_agent,
                )
                step.assigned_agent = fallback_agent

    def _fallback_heuristic_plan(
        self,
        title: str,
        description: str | None,
        agents: list[AgentData],
        explicit_agent: str | None,
    ) -> ExecutionPlan:
        """Heuristic fallback using keyword-based score_agent logic."""
        clean_title = title.strip() or "Untitled task"
        clean_description = (description or "").strip() or clean_title

        if explicit_agent and not is_lead_agent(explicit_agent):
            assigned_agent = explicit_agent
        elif explicit_agent and is_lead_agent(explicit_agent):
            assigned_agent = NANOBOT_AGENT_NAME
        else:
            keywords = extract_keywords(clean_title, clean_description)
            scored = [
                (agent, score_agent(agent, keywords)) for agent in agents if _is_delegatable(agent)
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

            if scored:
                assigned_agent = scored[0][0].name
            else:
                assigned_agent = self._fallback_agent_name(agents)

        if is_lead_agent(assigned_agent):
            assigned_agent = NANOBOT_AGENT_NAME

        return ExecutionPlan(
            steps=[
                ExecutionPlanStep(
                    temp_id="step_1",
                    title=clean_title,
                    description=clean_description,
                    assigned_agent=assigned_agent,
                    parallel_group=1,
                    order=1,
                )
            ]
        )
