# Nanobot Agent Schema Reference

## Required Fields

| Field | Type | Rules |
|-------|------|-------|
| `name` | string | Lowercase, alphanumeric + hyphens only. Pattern: `^[a-z0-9]+(-[a-z0-9]+)*$`. Must be unique. |
| `role` | string | Brief role description (e.g., "Senior Developer"). Cannot be empty. |
| `prompt` | string | Detailed system prompt. Becomes the agent's core instructions. Cannot be empty. |

## Optional Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `skills` | list[string] | `[]` | Capability tags for task routing. Use existing tags when possible. |
| `model` | string | system default | LLM model. Bare name or provider-prefixed. |
| `display_name` | string | auto-generated | Auto-converts `my-agent` → `My Agent` if omitted. |
| `soul` | string | auto-generated | Personality content. If omitted, written to `SOUL.md` in agent directory. |

## Known Models

| Model | Speed | Best For |
|-------|-------|----------|
| `claude-haiku-4-5` | Fastest | Simple, high-volume tasks |
| `claude-sonnet-4-6` | Balanced | Most tasks (recommended default) |
| `claude-opus-4-6` | Most capable | Complex reasoning, orchestration |

## Known Skills (use these for consistency)

**Development:** `coding`, `debugging`, `code-review`, `testing`, `refactoring`
**Research:** `research`, `summarization`, `analysis`, `fact-checking`
**Writing:** `writing`, `documentation`, `editing`, `copywriting`
**Data:** `data-analysis`, `visualization`, `statistics`, `sql`
**DevOps:** `ci-cd`, `docker`, `infrastructure`, `monitoring`, `deployment`
**Orchestration:** `task-routing`, `execution-planning`, `agent-coordination`, `escalation`
**General:** `planning`, `problem-solving`, `review`, `reporting`

## Built-in Presets (for reference)

```yaml
# developer
name: developer
role: Software Developer
skills: [coding, debugging, code-review, testing]

# researcher
name: researcher
role: Research Analyst
skills: [research, summarization, analysis]

# writer
name: writer
role: Technical Writer
skills: [writing, documentation, editing]

# data-analyst
name: data-analyst
role: Data Analyst
skills: [data-analysis, visualization, statistics]

# devops
name: devops
role: DevOps Engineer
skills: [ci-cd, docker, infrastructure, monitoring]

# lead-agent
name: lead-agent
role: Lead Agent — Orchestrator
skills: [task-routing, execution-planning, agent-coordination, escalation]
```

## Validation Rules

- `name` invalid chars auto-suggested: "My Agent" → "my-agent"
- `skills` must be YAML list, not a string
- `model` resolved to full provider prefix internally
- Agent stored at: `~/.nanobot/agents/{name}/config.yaml`

## Minimal Valid Example

```yaml
name: my-researcher
role: Research Analyst
prompt: |
  You are a research analyst specializing in market trends.
  You gather information from provided sources, analyze patterns,
  and produce clear findings with actionable insights.
skills:
  - research
  - analysis
  - summarization
model: claude-sonnet-4-6
```
