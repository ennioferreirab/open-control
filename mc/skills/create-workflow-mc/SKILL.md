---
name: create-workflow-mc
description: "Workflow designer for Mission Control. Use when the user wants to create a workflow, define an execution flow, or add a new workflow to an existing squad."
disable-model-invocation: true
---

# Create Workflow for Mission Control

Design and publish a workflow to an existing Mission Control squad.

This flow is terminal-first and focused:

1. Understand the workflow's purpose and select a squad.
2. Review the squad's agent roster.
3. Design workflow steps using those agents.
4. Publish after the design is complete.

Ask 1-2 questions at a time. Keep the flow structured, but do not dump a long questionnaire up front.

## Load Context First

Before starting, fetch the current workflow-authoring context:

```bash
curl -s http://localhost:3000/api/specs/workflow/context
```

Expected shape:

```json
{
  "publishedSquads": [
    {
      "squadSpecId": "k57a2dz1h3m9q0v7w8x6y5z4a1b2c3d4",
      "name": "content-creation",
      "displayName": "Content Creation",
      "description": "A squad that researches and writes long-form content",
      "agents": [
        {
          "key": "researcher",
          "name": "audience-researcher",
          "displayName": "Rafa Researcher",
          "role": "Audience researcher"
        },
        {
          "key": "writer",
          "name": "post-writer",
          "displayName": "Wanda Writer",
          "role": "Draft writer"
        },
        {
          "key": "reviewer",
          "name": "editorial-reviewer",
          "displayName": "Rita Reviewer",
          "role": "Editorial reviewer"
        }
      ],
      "existingWorkflows": [
        {
          "name": "default",
          "stepCount": 4
        }
      ]
    }
  ],
  "availableReviewSpecs": [
    {
      "id": "k57a2dz1h3m9q0v7w8x6y5z4a1b2c3d4",
      "name": "brief-quality-check",
      "scope": "task_output",
      "approvalThreshold": 0.8,
      "reviewerPolicy": "Senior reviewer",
      "rejectionRoutingPolicy": "Return to drafter"
    }
  ],
  "availableModels": ["claude-sonnet-4-6", "claude-opus-4-6"]
}
```

How to use it:

- Use `publishedSquads` to present squad options to the user.
- Use `agents` inside the selected squad to build the agent roster for step design.
- Use `existingWorkflows` to inform the user what workflows already exist on the squad.
- Use `availableReviewSpecs` when designing any `review` step. Never invent a textual `reviewSpecId`.
- Use `availableModels` for reference when discussing agent capabilities.

## Phase 1: Intent & Squad Selection

Understand the goal and select the target squad.

Collect:

- `workflow.name` — required slug: `^[a-z0-9]+(-[a-z0-9]+)*$`
- `workflow.description` — optional
  If the user has not provided a clear description, ask: "Can you summarize the workflow's purpose in one sentence?"
- `squadSpecId` — the squad this workflow belongs to

Start with:

- What should this workflow accomplish?
- What is the final output or deliverable?

Then present published squads from context as numbered options:

```text
Available squads:
  1. Content Creation (content-creation)
     Agents: 3 | Existing workflows: 1

  2. Software Delivery (software-delivery)
     Agents: 4 | Existing workflows: 0

Select a squad by number, or say "create new" to build one first.
```

If the user selects an existing squad, confirm the selection and move to Phase 2.

If the user says "create new":

1. Invoke `/create-squad-mc` — let it run through all its phases completely.
2. After squad creation completes, refresh context:

```bash
curl -s http://localhost:3000/api/specs/workflow/context
```

3. Present the updated squad list and let the user confirm the newly created squad.

Do not jump into step design yet.

## Phase 2: Agent Roster Review

Display the selected squad's agent roster before designing steps.

Present the roster in this format:

```text
Squad: "Content Creation" (content-creation)
Agents available for this workflow:
  [researcher]  audience-researcher | Rafa Researcher — Audience researcher
  [writer]      post-writer | Wanda Writer — Draft writer
  [reviewer]    editorial-reviewer | Rita Reviewer — Editorial reviewer
```

Notes:

- The bracketed key (e.g., `[researcher]`) is the `agentKey` used in step references.
- This flow does NOT create agents. Agents belong to the squad and are fixed.
- If the squad has no agents, stop and tell the user: the squad must have agents before a workflow can be designed. Offer to invoke `/create-squad-mc` to add agents.

Confirm with the user that they are ready to design steps.

## Phase 3: Step Design

Design steps one by one, or accept a batch proposal from the user.

Each step requires:

- `key` — unique slug within this workflow
- `type` — one of: `agent`, `human`, `checkpoint`, `review`, `system`
- `agentKey` — required for `agent` and `review` types; must match a key from the squad roster
- `title` — short human-readable description
- `dependsOn` — list of step keys this step waits for (omit if none)

For `review` steps, also require:

- `reviewSpecId` — must come from `availableReviewSpecs`; never fabricate this value
- `onReject` — the step key to return to on rejection

Default to explicit quality gates:

- Include a `review` step when the workflow produces generated output.
- Include a `human` step when output is externally important or irreversible.

If you add a `review` step and no suitable `availableReviewSpecs` exist, stop and ask the user whether to:

- Switch the step to `checkpoint` or `human` instead, or
- Create a review spec before continuing.

When presenting a review step, show the chosen review spec by name:

```text
3. [review]  review:reviewer — "Review the draft"
             review spec: brief-quality-check
             on reject: → draft
```

Show the exit criteria question after the steps are defined:

- What must be true for this workflow to be considered complete?

Present the full workflow in sequence before moving to Phase 4:

```text
Workflow: "content-pipeline"
  1. [research]  agent:researcher — "Research the target audience"
  2. [draft]     agent:writer — "Draft the deliverable" (depends on: research)
  3. [review]    review:reviewer — "Review the draft" (review spec: brief-quality-check, depends on: draft)
  4. [approve]   human — "Approve for publish" (depends on: review)

Exit Criteria: Final draft approved by human reviewer
```

Ask for confirmation before moving on.

## Phase 4: Review & Publish

Before publishing, show the full workflow summary:

```text
═══════════════════════════════════════
  Workflow Blueprint Summary
═══════════════════════════════════════
Workflow: {name}
Squad: {squad.displayName} ({squad.name})
Description: {description}

Steps ({count}):
  1. [{key}] {type}:{agentKey} — {title}
     ...

Exit Criteria: {exitCriteria}
═══════════════════════════════════════
```

Do not ask for approval to publish until the full summary has been shown.

On approval, publish with:

```bash
curl -s -X POST http://localhost:3000/api/specs/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "squadSpecId": "...",
    "workflow": {
      "name": "...",
      "description": "...",
      "steps": [
        {
          "key": "...",
          "type": "agent",
          "agentKey": "...",
          "title": "...",
          "dependsOn": ["..."]
        },
        {
          "key": "...",
          "type": "review",
          "agentKey": "...",
          "title": "...",
          "reviewSpecId": "...",
          "onReject": "...",
          "dependsOn": ["..."]
        },
        {
          "key": "...",
          "type": "human",
          "title": "...",
          "dependsOn": ["..."]
        }
      ],
      "exitCriteria": "..."
    }
  }'
```

Success response:

```json
{"success": true, "workflowSpecId": "..."}
```

Report the created `workflowSpecId` and offer next steps, such as testing the workflow or adding another workflow to the same squad.

## Contract Rules

- Workflow name must be a slug: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Step keys must be unique slugs within the workflow, matching `^[a-z0-9]+(-[a-z0-9]+)*$`
- `agent` and `review` steps must reference a valid `agentKey` from the selected squad's roster
- `review` steps must include `reviewSpecId` taken from `availableReviewSpecs`
- `review` steps must include `onReject` pointing to a valid step key
- Never fabricate `reviewSpecId` values
- Do not create agents or skills in this flow — agents belong to the squad
- Publish is the last step; never publish a workflow with unresolved review spec gaps
