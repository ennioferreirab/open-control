"""Plan parsing, extraction, and validation helpers for the task planner.

Provides functions to parse LLM plan responses into structured ExecutionPlan
objects, score agents against task keywords, build prompt components (agent
rosters, file summaries, task-shape hints), and normalize plan dependencies.

Extracted from planner.py per NFR21 (500-line module limit).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import json_repair

from mc.types import (
    HUMAN_AGENT_NAME,
    LEAD_AGENT_NAME,
    NANOBOT_AGENT_NAME,
    AgentData,
    ExecutionPlan,
    ExecutionPlanStep,
    is_lead_agent,
)
from mc.domain.utils import as_positive_int

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "and", "or", "but", "not", "this", "that", "it", "my", "your",
}

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

STANDARD_TOOLS = [
    "file I/O",
    "shell exec",
    "web search",
    "cron scheduling",
]

NON_DELEGATABLE_ROLES = {"remote-terminal"}


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


def _is_delegatable(agent: AgentData) -> bool:
    """Return True if an agent can receive delegated task steps.

    Excludes system agents, lead-agent, and non-delegatable roles
    (e.g. remote-terminal sessions) -- mirroring the dashboard's
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
            f"- **{agent.name}** -- {agent.role}\n"
            f"  Skills: {skills_str}\n"
            f"  Tools: {tools_str}"
        )
    if not lines:
        lines.append(
            f"- **nanobot** -- generalist executor\n"
            f"  Skills: general\n"
            f"  Tools: {tools_str}"
        )
    # Virtual agent for human-in-the-loop steps (always available)
    lines.append(
        f"- **{HUMAN_AGENT_NAME}** -- human operator\n"
        f"  Assign to steps that require manual review, approval, or human action.\n"
        f"  Human steps pause execution until a person accepts them."
    )
    return "\n".join(lines)


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
            as_positive_int(step.parallel_group, default=1) for step in independent_steps
        )

    for step in independent_steps:
        step.parallel_group = independent_group

    # Ensure dependent steps are always in a later group than dependencies.
    for _ in range(len(steps)):
        changed = False
        for step in steps:
            current = as_positive_int(step.parallel_group, default=independent_group)
            if not step.blocked_by:
                if current != independent_group:
                    step.parallel_group = independent_group
                    changed = True
                continue

            dep_groups = [
                as_positive_int(step_by_id[dep].parallel_group, default=independent_group)
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
            parallel_group=as_positive_int(
                s.get("parallel_group", s.get("parallelGroup")),
                default=1,
            ),
            order=as_positive_int(s.get("order"), default=index),
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


INLINE_PLANNING_SKILLS = frozenset({
    "writing-plans",
    "dispatching-parallel-agents",
})


def _load_lead_agent_planning_skills() -> tuple[list[str], str]:
    """Load configured lead-agent planning skills from the local skill workspace.

    Returns:
        Tuple of (configured_skill_names, inline_skill_content).

    The inline content is intentionally restricted to planning-relevant skills so
    the direct LLM planner path can benefit without injecting unrelated skills.
    """
    from nanobot.agent.skills import SkillsLoader

    from mc.infrastructure.agents.yaml_validator import validate_agent_file

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
