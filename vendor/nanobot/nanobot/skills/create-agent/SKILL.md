---
name: create-agent
description: Guided wizard to design and generate a nanobot agent configuration (config.yaml + optional SOUL.md). Use when creating a new agent, designing an agent from a description, or when the user asks to add an agent to Mission Control.
---

# Create Agent

Guided wizard for creating nanobot agent configurations. Walk through 5 steps conversationally — one question at a time.

## Workflow

```
Step 1: Intent Discovery   → understand what kind of agent is needed
Step 2: Agent Identity     → name, role, behavior mode, constraints
Step 3: Prompt Crafting    → build the system prompt collaboratively
Step 4: Config Finalization → model selection, final review
Step 5: Generate & Output  → write config.yaml + optional SOUL.md
```

## Step 1: Intent Discovery

Welcome the user and understand their starting point.

Present built-in presets as inspiration:

| Name | Role | Skills |
|------|------|--------|
| `developer` | Software Developer | coding, debugging, code-review, testing |
| `researcher` | Research Analyst | research, summarization, analysis |
| `writer` | Technical Writer | writing, documentation, editing |
| `data-analyst` | Data Analyst | data-analysis, visualization, statistics |
| `devops` | DevOps Engineer | ci-cd, docker, infrastructure, monitoring |

Ask: "What should this agent do?" and "Is there a preset close to what you need?"

- If preset selected: use as starting point, proceed
- If new use case: reflect understanding, ask ONE clarifying question if needed
- If unsure: ask "What task do you do repeatedly that takes too much time?"

## Step 2: Agent Identity

Collect four core decisions through natural conversation (1-2 questions at a time):

**A. Name** — slug format: `^[a-z0-9]+(-[a-z0-9]+)*$`. If they give "My Agent", suggest `my-agent`. Display name auto-generates if omitted.

**B. Role** — one specific sentence. "Developer" is too vague; "Python backend developer focused on API design" is better.

**C. Behavior mode:**
- **Executor**: does work itself (code, docs, analysis)
- **Orchestrator**: coordinates other agents, delegates
- **Hybrid**: mostly executes, can coordinate

**D. Scope and constraints** — ask what it should NOT do. Constraints are often more important than capabilities.

Present summary and confirm before proceeding.

## Step 3: Prompt Crafting

Generate a draft system prompt (150-400 words) using this structure:

```
You are [display_name], [role].

[2-3 sentences: identity, specialization, approach]

**Core responsibilities:**
- [responsibility 1]
- [responsibility 2]
- [responsibility 3]

**How you work:**
[Working style, methodology, quality standards]

**Scope:**
[What you handle vs. what you escalate]
```

Present the draft, ask for feedback, refine (minimum 1 round, max 3).

After prompt is confirmed, ask about **soul** (personality document):
- **Yes**: collect personality traits, values, communication style
- **No/Skip**: auto-generated soul template used

## Step 4: Config Finalization

Model selection:

| Model | Best For |
|-------|----------|
| `claude-haiku-4-5` | Fast, simple, high-volume tasks |
| `claude-sonnet-4-6` | Most tasks (recommended default) |
| `claude-opus-4-6` | Complex reasoning, orchestration |

Present complete config for final review. Handle last-minute changes.

## Step 5: Generate & Output

Write files directly to `~/.nanobot/agents/{agent-name}/`:

**config.yaml:**
```yaml
name: {agent-name}
role: "{agent-role}"
prompt: |
  {agent-prompt-indented-2-spaces}
skills:
  - {skill-1}
  - {skill-2}
```

Rules:
- `prompt` MUST use `|` literal block scalar, content indented 2 spaces
- Omit `display_name` if it's the auto-generated form of name
- Omit `model` if user chose system default
- Omit `skills` if no skills were specified

**SOUL.md** (if custom soul requested):
```markdown
# Soul

I am {display-name}, a nanobot agent.

## Role
{role}

## Personality
{traits as bullet points}

## Values
{values as bullet points}

## Communication Style
{communication description}
```

Also create `memory/` and `skills/` subdirectories.

Present success message with next options: create another, review/tweak, or done.

## Schema Reference

### Required Fields
| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Lowercase, alphanumeric + hyphens. Pattern: `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `role` | string | Brief role description. Cannot be empty. |
| `prompt` | string | Detailed system prompt. Cannot be empty. |

### Optional Fields
| Field | Type | Default |
|-------|------|---------|
| `skills` | list[string] | `[]` |
| `model` | string | system default |
| `display_name` | string | auto from name |
| `soul` | string | auto-generated |

### Known Skills
- **Development:** coding, debugging, code-review, testing, refactoring
- **Research:** research, summarization, analysis, fact-checking
- **Writing:** writing, documentation, editing, copywriting
- **Data:** data-analysis, visualization, statistics, sql
- **DevOps:** ci-cd, docker, infrastructure, monitoring, deployment
- **Orchestration:** task-routing, execution-planning, agent-coordination, escalation
