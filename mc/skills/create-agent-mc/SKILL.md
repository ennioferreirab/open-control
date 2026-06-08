---
name: create-agent-mc
description: guided mission control agent-spec builder and updater. use when the user wants to create, redesign, or update an agent spec, define responsibilities, choose skills and model, or publish a reusable agent configuration that follows the mission control agent schema.
disable-model-invocation: true
---

# Create or Update Agent for Mission Control

This skill builds agent specs that follow the Mission Control `agent` entity schema.

Keep the interaction conversational, but do not stay vague. The goal is a valid payload, not a brainstorm.

## Operating Modes

- **Create mode**: use when the user wants a new agent spec.
- **Update mode**: use when the user wants to improve an existing agent.

Pick the mode early and say which payload shape you are building.

## Required field discipline

Always collect or confirm:

- `name`
- `role`

In create mode, strongly prefer collecting the full operational shape:

- `displayName`
- `prompt`
- `soul`
- `skills`
- `model`
- `responsibilities`
- `nonGoals`
- `principles`
- `workingStyle`
- `qualityRules`
- `antiPatterns`
- `outputContract`
- `toolPolicy`
- `memoryPolicy`
- `executionPolicy`
- `reviewPolicyRef`

## Before assigning skills

Load the available skills catalog first. Never invent skill names.

```bash
curl -s http://localhost:3000/api/specs/skills?available=true
```

Present only relevant skills and explain why each one is a fit.

## Discovery sequence

Ask for the minimum information in this order:

1. What exact job the agent owns
2. What it must not do
3. What good output looks like
4. Which tools or skills it needs
5. Which review policy should gate its output

Prefer 1–2 questions at a time.

## Output design rules

The agent spec must be operational, not aspirational.

Good patterns:

- responsibilities are observable
- nonGoals are explicit
- principles resolve tradeoffs
- outputContract is concrete
- toolPolicy names when tools should or should not be used
- executionPolicy describes the working loop

Bad patterns:

- role is generic
- qualityRules are subjective only
- skills are guessed
- prompt duplicates the role without workflow

## Review before publish

Before calling the API, present a compact summary that includes:

- identity
- role
- model
- skills
- responsibilities
- nonGoals
- outputContract
- policies

Ask for confirmation only once the summary is concrete.

## Backend selection

If invoked with a `backend=<name>` argument (`codex` or `hermes`), set that as the new agent's backend:

- Include `"backend": "<name>"` in the POST payload.
- When `backend` is `hermes`, you MUST also ask the user for a `profile` (the Hermes profile directory name, e.g. provisioned via `scripts/hermes-provision-profile.sh`) and include `"profile": "<directory>"` in the payload.
- Omit `backend` and `profile` when the backend is `claude-code` (the default).

## API calls

Create:

```bash
curl -s -X POST http://localhost:3000/api/specs/agent       -H "Content-Type: application/json"       -d '{ ... }'
```

Update:

```bash
curl -s -X PATCH http://localhost:3000/api/specs/agent       -H "Content-Type: application/json"       -d '{ ... }'
```

Omit null or empty fields.

## Validation checklist

- `name` is a slug
- `role` is specific
- all skill names exist in the catalog
- policies do not contradict each other
- outputContract is concrete enough for downstream review
- prompt and soul do not fight each other
