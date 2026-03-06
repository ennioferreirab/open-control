"""LLM-based task planner for intelligent agent routing.

Decomposes tasks into structured execution plans using LLM reasoning
instead of keyword-matching heuristics. Falls back to heuristic planning
on LLM failure.

Created for Story 4.5 — extracted from orchestrator.py per NFR21
(500-line module limit).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path

import json_repair

from mc.types import (
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
INLINE_PLANNING_SKILLS = frozenset({
    "writing-plans",
    "dispatching-parallel-agents",
})

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "and", "or", "but", "not", "this", "that", "it", "my", "your",
}

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


BATCH_ITEM_CUES = (
    "video", "videos", "youtube", "file", "files", "url", "urls", "link",
    "links", "document", "documents", "doc", "docs", "page", "pages",
    "article", "articles", "channel", "channels", "source", "sources",
    "commit", "commits", "issue", "issues", "ticket", "tickets",
    "post", "posts", "episode", "episodes", "transcript", "transcripts",
    "canal", "canais", "arquivo", "arquivos", "documento", "documentos",
    "pagina", "paginas", "artigo", "artigos", "fonte", "fontes",
    "tarefa", "tarefas", "transcricao", "transcricoes",
)

ORDERING_CUES = (
    "latest", "recent", "newest", "last", "top",
    "ultimos", "ultimas", "mais recentes", "recentes",
)


def extract_keywords(title: str, description: str | None = None) -> list[str]:
    """Extract meaningful keywords from task text.

    Tokenizes on non-alphanumeric characters, removes stopwords and
    tokens shorter than 3 characters.
    """
    text = title.lower()
    if description:
        text += " " + description.lower()
    tokens = re.split(r"[^a-z0-9]+", text)
    return [t for t in tokens if t and len(t) > 2 and t not in STOPWORDS]


def score_agent(agent: AgentData, keywords: list[str]) -> float:
    """Score an agent based on skill tag overlap with task keywords.

    Exact matches score 1.0 per keyword. Partial matches (keyword
    contained in skill or vice versa) score 0.5 each.
    """
    if not agent.skills or not keywords:
        return 0.0
    agent_skills_lower = {s.lower() for s in agent.skills}
    score = 0.0
    for kw in keywords:
        if kw in agent_skills_lower:
            score += 1.0
            continue
        for skill in agent_skills_lower:
            if kw in skill or skill in kw:
                score += 0.5
                break
    return score


def _extract_requested_item_count(title: str, description: str | None = None) -> int | None:
    """Extract a small explicit item count from user text, if present.

    Restricts matches to 2..20 to avoid treating years and large numeric amounts
    as a batching signal.
    """
    text = f"{title} {description or ''}"
    for match in re.finditer(r"\b(\d{1,2})\b", text):
        count = int(match.group(1))
        if 2 <= count <= 20:
            return count
    return None


def _build_task_shape_hints(title: str, description: str | None = None) -> str:
    """Build extra prompt hints for tasks that likely benefit from batching."""
    text = f"{title} {description or ''}".lower()
    item_count = _extract_requested_item_count(title, description)
    has_batch_cue = item_count is not None and any(
        cue in text for cue in (*BATCH_ITEM_CUES, *ORDERING_CUES)
    )
    if not has_batch_cue:
        return ""

    hints = [
        f"- The user explicitly asked for {item_count} items. If those items can be processed independently, create separate item-level steps so they can run in parallel.",
        "- Preserve the requested selection rule explicitly in the plan (for example: latest/recent/top N, first N, or named URLs/files).",
        "- Add a final aggregation or synthesis step blocked by every item-level step.",
        "- Each item-level step should produce a distinct output artifact that a downstream synthesis step can combine.",
    ]
    return "Task structure hints:\n" + "\n".join(hints)


def _load_lead_agent_planning_skills() -> tuple[list[str], str]:
    """Load configured lead-agent planning skills from the local skill workspace.

    Returns:
        Tuple of (configured_skill_names, inline_skill_content).

    The inline content is intentionally restricted to planning-relevant skills so
    the direct LLM planner path can benefit without injecting unrelated skills.
    """
    from nanobot.agent.skills import SkillsLoader

    from mc.yaml_validator import validate_agent_file

    config_file = Path.home() / ".nanobot" / "agents" / LEAD_AGENT_NAME / "config.yaml"
    if not config_file.exists():
        return [], ""

    result = validate_agent_file(config_file)
    if isinstance(result, list):
        return [], ""

    configured_skills = list(result.skills or [])
    if not configured_skills:
        return [], ""

    inline_skill_names = [
        name for name in configured_skills
        if name in INLINE_PLANNING_SKILLS
    ]
    if not inline_skill_names:
        return configured_skills, ""

    loader = SkillsLoader(
        workspace=config_file.parent,
        global_skills_dir=Path.home() / ".nanobot" / "workspace" / "skills",
    )
    inline_content = loader.load_skills_for_context(inline_skill_names)
    return configured_skills, inline_content


def _build_file_summary(files: list[dict]) -> str:
    """Build a human-readable file summary for lead agent context (FR-F28, FR-F29).

    Includes file names, MIME types, sizes, and total size so the Lead Agent
    can consider file types when routing steps to agents.
    """
    if not files:
        return ""

    def _human_size(b: int) -> str:
        return f"{b // 1024} KB" if b < 1_048_576 else f"{b / 1_048_576:.1f} MB"

    total = sum(f.get("size", 0) for f in files)
    names = ", ".join(
        f"{f['name']} ({f.get('type', 'application/octet-stream')}, {_human_size(f.get('size', 0))})"
        for f in files
    )
    return (
        f"Task has {len(files)} attached file(s) (total {_human_size(total)}): {names}. "
        f"Consider file types when selecting the best agent."
    )


STANDARD_TOOLS = [
    "file I/O",
    "shell exec",
    "web search",
    "cron scheduling",
]


NON_DELEGATABLE_ROLES = {"remote-terminal"}


def _is_delegatable(agent: AgentData) -> bool:
    """Return True if an agent can receive delegated task steps.

    Excludes system agents, lead-agent, and non-delegatable roles
    (e.g. remote-terminal sessions) — mirroring the dashboard's
    useSelectableAgents hook.
    """
    if getattr(agent, "is_system", False):
        return False
    if is_lead_agent(agent.name):
        return False
    if getattr(agent, "role", "") in NON_DELEGATABLE_ROLES:
        return False
    return True


def _build_agent_roster(agents: list[AgentData]) -> str:
    """Build the agent roster string for the LLM prompt.

    Non-delegatable agents are excluded so the LLM never sees them
    as candidate assignees.
    """
    tools_str = ", ".join(STANDARD_TOOLS)
    lines = []
    for agent in agents:
        if not _is_delegatable(agent):
            continue
        skills_str = ", ".join(agent.skills) if agent.skills else "general"
        lines.append(
            f"- **{agent.name}** — {agent.role}\n"
            f"  Skills: {skills_str}\n"
            f"  Tools: {tools_str}"
        )
    if not lines:
        lines.append(
            f"- **nanobot** — generalist executor\n"
            f"  Skills: general\n"
            f"  Tools: {tools_str}"
        )
    return "\n".join(lines)


def _as_positive_int(value: object, default: int) -> int:
    """Return a positive integer from a loose input value."""
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _as_string_list(value: object) -> list[str]:
    """Normalize scalar/list input into a list of non-empty strings."""
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_plan_dependencies_and_groups(steps: list[ExecutionPlanStep]) -> None:
    """Validate blockedBy references and normalize parallel groups."""
    step_by_id = {step.temp_id: step for step in steps}
    valid_ids = set(step_by_id.keys())

    # Keep only valid, non-self dependencies.
    for step in steps:
        invalid = [
            dep for dep in step.blocked_by
            if dep not in valid_ids or dep == step.temp_id
        ]
        if invalid:
            logger.warning(
                "[planner] Step '%s' had invalid blockedBy refs %s; dropping them",
                step.temp_id,
                invalid,
            )
        step.blocked_by = [
            dep for dep in step.blocked_by
            if dep in valid_ids and dep != step.temp_id
        ]

    # All independent steps share the same group number.
    independent_steps = [step for step in steps if not step.blocked_by]
    independent_group = 1
    if independent_steps:
        independent_group = min(
            _as_positive_int(step.parallel_group, 1) for step in independent_steps
        )

    for step in independent_steps:
        step.parallel_group = independent_group

    # Ensure dependent steps are always in a later group than dependencies.
    for _ in range(len(steps)):
        changed = False
        for step in steps:
            current = _as_positive_int(step.parallel_group, independent_group)
            if not step.blocked_by:
                if current != independent_group:
                    step.parallel_group = independent_group
                    changed = True
                continue

            dep_groups = [
                _as_positive_int(step_by_id[dep].parallel_group, independent_group)
                for dep in step.blocked_by
                if dep in step_by_id
            ]
            required_group = (max(dep_groups) + 1) if dep_groups else independent_group + 1
            if current < required_group:
                step.parallel_group = required_group
                changed = True
            else:
                step.parallel_group = current
        if not changed:
            break


def _parse_plan_response(raw: str) -> ExecutionPlan:
    """Parse LLM response into ExecutionPlan, tolerating common LLM JSON wrappers."""
    text = raw.strip()
    if not text:
        raise ValueError("LLM response was empty")

    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = json_repair.loads(text)

    data = _normalize_plan_payload(data)
    if "steps" not in data or not data["steps"]:
        raise ValueError("LLM response missing 'steps' key or empty steps")

    steps: list[ExecutionPlanStep] = []
    for index, s in enumerate(data["steps"], start=1):
        temp_id = (
            s.get("temp_id")
            or s.get("tempId")
            or s.get("step_id")
            or s.get("stepId")
            or f"step_{index}"
        )
        title = s.get("title") or s.get("description") or f"Step {index}"
        description = s.get("description") or title
        assigned_agent = (
            s.get("assigned_agent")
            or s.get("assignedAgent")
            or NANOBOT_AGENT_NAME
        )
        blocked_by = _as_string_list(
            s.get("blocked_by")
            or s.get("blockedBy")
            or s.get("depends_on")
            or s.get("dependsOn")
        )

        steps.append(ExecutionPlanStep(
            temp_id=str(temp_id),
            title=str(title),
            description=str(description),
            assigned_agent=str(assigned_agent),
            blocked_by=blocked_by,
            parallel_group=_as_positive_int(
                s.get("parallel_group", s.get("parallelGroup")),
                1,
            ),
            order=_as_positive_int(s.get("order"), index),
        ))

    _normalize_plan_dependencies_and_groups(steps)

    return ExecutionPlan(steps=steps)


def _normalize_plan_payload(data: object) -> dict[str, object]:
    """Normalize common LLM response shapes into {'steps': [...]}."""
    if isinstance(data, list):
        return {"steps": data}

    if not isinstance(data, dict):
        raise ValueError(f"LLM response is not a JSON object/list: {type(data).__name__}")

    steps = data.get("steps")
    if isinstance(steps, list) and steps:
        return data

    # Some models wrap the actual plan in another object.
    for key in ("plan", "execution_plan", "executionPlan", "updated_plan", "updatedPlan", "data", "result"):
        nested = data.get(key)
        if isinstance(nested, dict):
            nested_steps = nested.get("steps")
            if isinstance(nested_steps, list) and nested_steps:
                return nested
        elif isinstance(nested, list) and nested:
            return {"steps": nested}

    # Last-resort: treat a single step object as a one-step plan.
    if any(k in data for k in ("assignedAgent", "assigned_agent", "description", "title", "tempId", "step_id")):
        return {"steps": [data]}

    return data


class TaskPlanner:
    """Plans task execution using LLM reasoning."""

    def __init__(self, bridge: object | None = None) -> None:
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
        try:
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
        except asyncio.TimeoutError:
            logger.warning(
                "[planner] LLM planning timed out after %ds, using heuristic fallback",
                LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "[planner] LLM planning failed (%s), using heuristic fallback",
                type(exc).__name__,
                exc_info=True,
            )

        plan = self._fallback_heuristic_plan(
            title, description, agents, explicit_agent
        )
        self._validate_agent_names(plan, agents)
        self._prevent_lead_agent_steps(plan, agents)
        logger.info(
            "[planner] Planned task via heuristic fallback in %.2fs (%d steps)",
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

        from mc.provider_factory import create_provider

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

        from mc.ask_user.handler import AskUserHandler
        from mc.orientation import load_orientation

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

    def _validate_agent_names(
        self, plan: ExecutionPlan, agents: list[AgentData]
    ) -> None:
        """Replace invalid/disallowed agent names with nanobot."""
        fallback_agent = self._fallback_agent_name(agents)
        delegatable_names = {a.name for a in agents if _is_delegatable(a)} | {NANOBOT_AGENT_NAME}
        for step in plan.steps:
            if (
                not step.assigned_agent
                or step.assigned_agent not in delegatable_names
            ):
                if step.assigned_agent:
                    logger.warning(
                        "[planner] Invalid/disallowed agent '%s' on step '%s', "
                        "replacing with '%s'",
                        step.assigned_agent,
                        step.temp_id,
                        fallback_agent,
                    )
                step.assigned_agent = fallback_agent

    def _override_agents(self, plan: ExecutionPlan, agent_name: str) -> None:
        """Override all step assignments with an explicit agent."""
        assigned_name = (
            NANOBOT_AGENT_NAME if is_lead_agent(agent_name) else agent_name
        )
        if assigned_name != agent_name:
            logger.warning(
                "[planner] Explicit lead-agent override replaced with '%s' "
                "(pure orchestrator invariant)",
                assigned_name,
            )
        for step in plan.steps:
            step.assigned_agent = assigned_name

    def _fallback_agent_name(self, agents: list[AgentData]) -> str:
        """Choose a non-lead fallback agent name."""
        return NANOBOT_AGENT_NAME

    def _prevent_lead_agent_steps(
        self, plan: ExecutionPlan, agents: list[AgentData]
    ) -> None:
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
                (agent, score_agent(agent, keywords))
                for agent in agents
                if _is_delegatable(agent)
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

            assigned_agent = (
                scored[0][0].name
                if scored and scored[0][1] > 0
                else NANOBOT_AGENT_NAME
            )

        if is_lead_agent(assigned_agent):
            assigned_agent = NANOBOT_AGENT_NAME

        return ExecutionPlan(steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title=clean_title,
                description=clean_description,
                assigned_agent=assigned_agent,
                parallel_group=1,
                order=1,
            )
        ])
