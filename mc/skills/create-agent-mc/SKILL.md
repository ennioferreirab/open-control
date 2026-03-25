---
name: create-agent-mc
description: "Guided wizard to design and publish an agent specification to Mission Control. Use this skill whenever the user wants to create a new agent, add an agent to MC, design an agent from a description, says 'new agent', 'create agent', 'add agent', or asks about building a specialist agent for their team."
disable-model-invocation: true
---

# Create Agent for Mission Control

Walk the user through designing an agent specification conversationally, then publish it to Mission Control via the dashboard API.

The conversation follows 4 phases. Keep it natural — ask 1-2 questions at a time, never dump a form.

## Phase 1: Discovery & Identity

Start by understanding what the user needs. Present presets as inspiration:

| Preset | Role | Skills |
|--------|------|--------|
| `developer` | Software Developer | coding, debugging, code-review, testing |
| `researcher` | Research Analyst | research, summarization, analysis |
| `writer` | Technical Writer | writing, documentation, editing |
| `data-analyst` | Data Analyst | data-analysis, visualization, statistics |
| `devops` | DevOps Engineer | ci-cd, docker, infrastructure, monitoring |

Ask what this agent should do and if a preset is close.

Then collect identity:
- **Name** — slug format (`^[a-z0-9]+(-[a-z0-9]+)*$`). Suggest one from their description.
- **Display Name** — human-readable. Optional — if omitted, the UI generates initials from the name slug (e.g., `brand-reviewer` → "BR").
- **Role** — one specific sentence. "Developer" is too vague; "Python backend developer focused on API design" is better.

Confirm before proceeding.

## Phase 2: Behavior & Responsibilities

Collect through natural conversation:

- **Responsibilities** (required) — What this agent does. Each item should be actionable.
  Example: `["Write clean, well-tested Python code", "Review PRs for correctness"]`
- **Non-Goals** (optional) — What it should NOT do. Often more important than capabilities.
  Example: `["Do not deploy to production", "Do not make infra changes"]`
- **Principles** (optional) — Guiding values for decision-making.
  Example: `["Prefer simplicity over cleverness", "Test before you ship"]`
- **Working Style** (optional) — How the agent approaches work.
  Example: `"Methodical. Breaks problems into small steps. Asks clarifying questions first."`

Confirm the behavioral summary.

## Load Available Skills

Before assigning skills, fetch the catalog:

```bash
curl -s http://localhost:3000/api/specs/skills?available=true
```

Use the returned `skills` array to present valid options. Do not invent skill
names — only assign skills that exist in the catalog.

## Phase 3: Guardrails & Config (condensed — skip if not needed)

Ask: "Do you want to configure quality rules, policies, or model selection? These are optional — I can use sensible defaults."

If yes, collect any of these the user cares about:
- **Quality Rules** — standards to meet (e.g., ">80% test coverage")
- **Anti-Patterns** — things to avoid (e.g., "no global state")
- **Output Contract** — expected output format
- **Tool Policy** — rules about tool usage
- **Memory Policy** — context/memory handling
- **Execution Policy** — how tasks are executed
- **Model** — `claude-haiku-4-5` (fast), `claude-sonnet-4-6` (default), `claude-opus-4-6` (complex)
- **Skills** — from the skills catalog fetched above (use real names only)
- **Review Policy Ref** — reference to a review policy

## Phase 4: Review & Publish

Present a clear summary:

```
═══════════════════════════════════════
  Agent Specification Summary
═══════════════════════════════════════
  Name:         {name}
  Display Name: {displayName}
  Role:         {role}

  Responsibilities:
    - {each responsibility}

  Non-Goals:     {if any}
  Principles:    {if any}
  Working Style: {if set}
  Quality Rules: {if any}
  Anti-Patterns: {if any}
  Model:         {if set}
  Skills:        {if any}
═══════════════════════════════════════
```

On confirmation, publish via Bash:

```bash
curl -s -X POST http://localhost:3000/api/specs/agent \
  -H "Content-Type: application/json" \
  -d '{ "name": "...", "displayName": "...", "role": "...", ... }'
```

Only include fields that were collected — omit null/empty fields from the JSON.

A response of `{"success": true, "specId": "..."}` means it worked. Report the result and offer to create another agent or finish.

## Schema Reference

### Required
| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Lowercase slug: `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `role` | string | Brief role description |

### Optional
| Field | Type | Notes |
|-------|------|-------|
| `displayName` | string | Human-readable name. If omitted, UI generates initials from slug. |
| `responsibilities` | string[] | |
| `nonGoals` | string[] |
| `principles` | string[] |
| `workingStyle` | string |
| `qualityRules` | string[] |
| `antiPatterns` | string[] |
| `outputContract` | string |
| `toolPolicy` | string |
| `memoryPolicy` | string |
| `executionPolicy` | string |
| `reviewPolicyRef` | string |
| `skills` | string[] |
| `model` | string |
