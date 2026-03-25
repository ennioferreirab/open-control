---
name: create-squad-mc
description: "Skills-first architect for Mission Control squads. Use this whenever the user wants to create a squad, design a multi-agent team, define a workflow, set up a reusable team of agents, or publish a squad blueprint to Mission Control."
disable-model-invocation: true
---

# Create Squad for Mission Control

Design and publish a squad blueprint to Mission Control.

This flow is terminal-first and skills-first:

1. Understand the outcome.
2. Discover the capabilities, skills, and operating patterns the squad needs.
3. Reuse existing agents and skills where possible.
4. Create missing skills before publish when they do not already exist.
5. Design the minimum viable roster and workflow.
6. Audit skill coverage — verify every agent has the skills it needs.
7. Publish only after the audit passes with zero issues.

Ask 1-2 questions at a time. Keep the flow structured, but do not dump a long questionnaire up front.

## Load Context First

Before deep discovery, fetch both the squad-authoring context and the full skills
catalog. You need both — squad context provides agents, review specs, and models;
the skills endpoint provides the complete and up-to-date skills catalog.

```bash
curl -s http://localhost:3000/api/specs/squad/context
curl -s http://localhost:3000/api/specs/skills
```

### Squad context shape

```json
{
  "activeAgents": [
    {
      "name": "writer-agent",
      "displayName": "Writer Agent",
      "role": "Content writer",
      "prompt": "Write concise content",
      "model": "claude-sonnet-4-6",
      "skills": ["writing", "editing"],
      "soul": "..."
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

### Skills catalog shape

```json
{
  "skills": [
    {
      "name": "writing",
      "description": "Create clear written content",
      "source": "workspace",
      "available": true,
      "always": false,
      "supportedProviders": ["claude-code", "nanobot"],
      "requires": null,
      "metadata": { "categories": ["content"] }
    }
  ]
}
```

Skills have `available: true` when usable, or `available: false` with `requires`
explaining what is missing.

### How to use the loaded context

- Use `activeAgents` to identify reuse candidates.
- Use the skills catalog to assign skills, check availability, and verify
  provider compatibility.
- Use `available: false` skills to distinguish skills that exist but are
  unavailable because requirements are missing — do not create duplicates.
- Use `availableReviewSpecs` when designing any `review` workflow step. Never
  invent a textual `reviewSpecId`.
- Use `supportedProviders` to confirm whether a skill is already adapted for the
  provider this squad will run on.
- Use `availableModels` for every new agent.

If you create a missing skill during the flow, refresh the skills catalog to
confirm registration:

```bash
curl -s http://localhost:3000/api/specs/skills
```

Then continue with the refreshed catalog.

## Phase 1: Intent

Understand what the squad is for.

Collect:

- `squad.name` - required slug: `^[a-z0-9]+(-[a-z0-9]+)*$`
- `squad.displayName` - optional human name (UI generates from name slug if omitted)
- `squad.description` - optional
- `squad.outcome` - optional but strongly recommended

Start with:

- What should this squad accomplish?
- What is the final outcome or deliverable?

Do not jump into agents yet.

## Phase 2: Capability, Skills, and Pattern Discovery

Before designing the roster, explicitly identify:

- the core capabilities the squad needs
- the required skills behind those capabilities
- the operating pattern the squad should follow
- the quality and approval checkpoints

Produce a compact discovery summary before moving on:

```text
Required capabilities:
  1. Audience research
  2. Long-form drafting
  3. Editorial review

Required skills:
  1. research-synthesis
  2. writing
  3. editorial-review

Operating pattern:
  research -> draft -> review -> human approval

Quality gates:
  - reviewer must check factual accuracy
  - human approval before publish
```

Also determine the **target provider** for this squad's runtime if it is not
already obvious from the current session:

- `claude-code`
- `codex`
- `nanobot`

Use skills as the primary planning unit. Agents exist to own capabilities implemented through skills.

When inferring patterns, prefer the simplest workable pattern:

- Software delivery: plan -> implement -> review -> approval
- Research: research -> synthesize -> review
- Content: research -> draft -> review -> approval
- Operations: intake -> execute -> verify -> report

## Phase 3: Skill Resolution

Resolve every required skill before finalizing the squad.

For each required skill:

1. If it exists in the skills catalog with `available: true`, reuse it.
2. If it exists in the skills catalog with `available: false`:
   - explain why it is unavailable using `requires`
   - ask whether to satisfy the requirement now or choose a different skill
   - do not create a duplicate skill with the same purpose
3. If it does not exist at all:
   - **do not create it silently** — present a summary first (see below)
   - only create after explicit user confirmation

When one or more skills need to be created, present them all together before
starting any creation:

```text
This squad requires N skill(s) that don't exist yet:

  1. research-synthesis
     Purpose: Synthesize research findings into structured reports
     Resources: references/ (output format spec)
     How it works: Agent receives raw research notes, extracts key findings,
     and produces a structured markdown report with sections for summary,
     evidence, and recommendations.

  2. editorial-review
     Purpose: Review written content for clarity, tone, and factual accuracy
     Resources: references/ (quality rubric)
     How it works: Agent receives a draft, scores it against a rubric
     (clarity, accuracy, tone, structure), and returns detailed feedback
     with suggested edits.

Do you want me to create these N skills now? I'll use /create-skill-mc for each.
```

On confirmation, invoke `/create-skill-mc` for each missing skill. After all
skills are created, refresh the skills catalog to confirm registration:

```bash
curl -s http://localhost:3000/api/specs/skills
```

Provider compatibility rule:

- before assigning a skill to an agent, check whether the skill's
  `supportedProviders` includes the target provider
- if the skill does not yet support the target provider, stop and ask the user
  whether they want to add compatibility for that skill to that provider first
- do not silently assign a skill to an unsupported provider

Example:

```text
Skill "writing" exists and is available, but it is adapted only for:
  - claude-code
  - nanobot

This squad is targeting:
  - codex

Do you want to add Codex compatibility to "writing" now before I assign it?
```

### Missing Skill Creation

Delegate to `/create-skill-mc` for each missing skill. Do not scaffold or write
skills manually — the skill wizard handles structure, validation, and sync.

## Phase 4: Agent Design

Only after capabilities and skills are resolved, design the roster.

### Agent Reuse Priority (Mandatory)

ALWAYS prefer reusing existing agents over creating new ones. Too many agents
cause confusion and fragmentation. Only create a new agent when NO existing
agent is a credible match for the required capability.

Before proposing any roster, you MUST produce a Reuse Assessment for every
required capability identified in Phase 2. Evaluate each capability against
the `activeAgents` list from the context loaded in the "Load Context First"
step above.

The example below uses hypothetical agents for illustration — your actual
assessment must reference the real agents returned by the context endpoint:

```text
Reuse Assessment:
  Capability "audience research":
    Match: researcher-agent (85% fit) — has research-synthesis skill, used in content squads
    Recommendation: REUSE

  Capability "long-form drafting":
    Match: post-writer (90% fit) — has writing skill, same model target
    Recommendation: REUSE

  Capability "social distribution":
    Match: content-scheduler (55% fit) — has scheduling skill, but no social-specific tools
    Recommendation: ASK — present to user for decision

  Capability "editorial review":
    Match: none — no existing agent with editorial-review skill
    Recommendation: CREATE NEW
```

Rules:
- A match of 60%+ fit means REUSE. Present the candidate and confirm with the user.
- A partial match (40-59%) means ASK — show the candidate and let the user decide.
- Below 40% or no match means CREATE NEW is acceptable.
- **Hard rule:** if you would create 3 or more new agents, STOP. List all
  proposed new agents, explain why existing agents cannot be reused for each,
  and get explicit user confirmation before proceeding.

Minimize agent count. Reuse existing agents whenever the fit is credible.

Every squad role needs:

- `key` - workflow reference key
- `name` - stable functional slug
- `displayName` - optional human-facing name (UI generates initials from slug if omitted)
- `role` - short role summary
- `prompt`
- `model`
- `skills`
- `soul`

### Naming Standard

For every new agent:

- `name` stays functional and slug-safe
- `displayName` should be memorable and human, inspired by the Opensquad style
- Prefer light alliteration or a strong functional persona when it improves recall

Examples:

- `displayName: "Rafa Researcher"` with `name: "audience-researcher"`
- `displayName: "Wanda Writer"` with `name: "post-writer"`
- `displayName: "Diego Dev"` with `name: "feature-developer"`

Do not use joke names that obscure the agent's purpose.

### Reuse Rules

Reuse is the default. For every capability, the Reuse Assessment above determines the action:

1. Show the candidate and explain why it matches.
2. Ask whether to reuse it.
3. If reused:
   - preserve its existing `name`
   - include `reuseName`
   - preserve its existing prompt/model/skills/soul contract

For every new agent, the final payload must explicitly include:

- `displayName`
- `prompt`
- `model`
- `skills`
- `soul`

Never leave those implicit. If `skills` is intentionally empty, say so explicitly. If `soul` is short, still make it explicit.

Present the roster before moving on:

```text
Agents (3):
  [researcher] audience-researcher | Rafa Researcher
    role: Audience researcher
    model: claude-sonnet-4-6
    skills: research-synthesis, interviewing

  [writer] post-writer | Wanda Writer
    role: Draft writer
    model: claude-sonnet-4-6
    skills: writing

  [reviewer] editorial-reviewer | Rita Reviewer
    role: Editorial reviewer
    model: claude-opus-4-6
    skills: editorial-review
```

## Phase 5: Workflow and Review Design

Design the workflow after the roster is stable.

Each workflow step needs:

- `key`
- `type`: `agent`, `human`, `review`, or `system`
- `agentKey` when type is `agent` or `review`
- `title`
- `dependsOn` when needed
- `reviewSpecId` and `onReject` for review steps

Also collect:

- workflow name
- exit criteria
- review policy

Default to explicit quality gates:

- include a reviewer when there is generated output
- include a human approval step when the output is externally important

Review-step rule:

- if you add a `review` step, select a real `reviewSpecId` from
  `availableReviewSpecs`
- show the chosen review spec by name when presenting the workflow
- if no suitable `availableReviewSpecs` exist, stop and ask the user whether to:
  - switch the step to `human`, or
  - create a new review spec (see "Creating a Review Spec" below)
- never fabricate identifiers like `brief-quality-check` as `reviewSpecId`

### Creating a Review Spec

When no existing review spec fits the workflow's needs, create one via the API.

First, collaborate with the user to define:

- **name** — slug-safe identifier (e.g., `content-quality-check`)
- **scope** — `agent`, `workflow`, or `execution`
- **criteria** — at least one criterion with `id`, `label`, `weight` (0-1),
  and optional `description`
- **approvalThreshold** — number between 0 and 1 (e.g., 0.8 means 80% score
  required to pass)
- **vetoConditions** (optional) — conditions that auto-reject regardless of score
- **feedbackContract** (optional) — description of expected feedback format
- **reviewerPolicy** (optional) — who performs the review (e.g., `"lead-agent"`)
- **rejectionRoutingPolicy** (optional) — what happens on rejection

Present the review spec before creating:

```text
═══════════════════════════════════════
  New Review Spec
═══════════════════════════════════════
Name: content-quality-check
Scope: workflow
Approval threshold: 0.8

Criteria:
  1. accuracy (weight: 0.4) — Factual correctness of all claims
  2. clarity (weight: 0.3) — Clear and understandable writing
  3. completeness (weight: 0.3) — All required sections present

Veto conditions:
  - Plagiarized content detected

Reviewer policy: lead-agent
═══════════════════════════════════════
```

On user confirmation, create via:

```bash
curl -s -X POST http://localhost:3000/api/specs/review-spec \
  -H "Content-Type: application/json" \
  -d '{
    "name": "content-quality-check",
    "scope": "workflow",
    "criteria": [
      { "id": "accuracy", "label": "Accuracy", "weight": 0.4, "description": "Factual correctness of all claims" },
      { "id": "clarity", "label": "Clarity", "weight": 0.3, "description": "Clear and understandable writing" },
      { "id": "completeness", "label": "Completeness", "weight": 0.3, "description": "All required sections present" }
    ],
    "approvalThreshold": 0.8,
    "vetoConditions": ["Plagiarized content detected"],
    "reviewerPolicy": "lead-agent"
  }'
```

MCP agents can also use the `create_review_spec` tool directly with the same
fields.

Success response:

```json
{"success": true, "specId": "k57a2dz1..."}
```

After creation, refresh context to get the new review spec ID:

```bash
curl -s http://localhost:3000/api/specs/squad/context
```

Use the returned `specId` as the `reviewSpecId` for the review step.

Present the workflow in sequence:

```text
Workflow: "default"
  1. [research] agent:researcher - "Research the target audience"
  2. [draft]    agent:writer - "Draft the deliverable" (depends on: research)
  3. [review]   review:reviewer - "Review the draft" (review spec: brief-quality-check, depends on: draft)
  4. [approve]  human - "Approve for publish" (depends on: review)
```

## Phase 6: Skill Coverage Audit

After the workflow is stable, audit every agent-step to confirm that skill
assignments are complete and that no agent will launch "empty-handed".

### Procedure

1. For each workflow step of type `agent` or `review`, identify the assigned agent.
2. For each assigned agent, list the skills from its roster entry (Phase 4).
3. Cross-reference each skill against the current skills catalog (re-fetch via
   `/api/specs/skills` if any skills were created during this flow).
4. For each workflow step of type `review`, verify it includes `reviewSpecId`
   (from `availableReviewSpecs`) and `onReject` routing policy.
5. Flag any of the following problems:
   - **No skills assigned** — agent has `skills: []` or skills were omitted.
   - **Skill not found** — skill name is not in the skills catalog.
   - **Provider mismatch** — skill exists but does not support the target provider.
   - **Capability gap** — the step's purpose (from Phase 5) requires a capability
     identified in Phase 2, but no assigned skill covers it.
   - **Missing reviewSpecId** — a `review` step has no `reviewSpecId` or uses a
     fabricated ID not in `availableReviewSpecs`.
   - **Missing onReject** — a `review` step has no `onReject` routing policy.

Present the audit result using this format:

```text
═══════════════════════════════════════
  Skill Coverage Audit
═══════════════════════════════════════
Step [research] → agent:researcher (Rafa Researcher)
  ✓ research-synthesis — available, provider OK
  ✓ interviewing — available, provider OK

Step [draft] → agent:writer (Wanda Writer)
  ✓ writing — available, provider OK

Step [review] → review:reviewer (Rita Reviewer)
  ✓ editorial-review — available, provider OK
  ✗ reviewSpecId — MISSING (required for review steps)
    → Action: select from availableReviewSpecs or create one
  ✗ onReject — MISSING (required for review steps)
    → Action: define routing policy (e.g., "return_to_step:draft")

Step [approve] → human
  (no agent — skip)

Summary: 2 issue(s) found
═══════════════════════════════════════
```

### Resolution

- If all checks pass, proceed to Phase 7.
- If any issue is found, resolve it before continuing:
  - **No skills assigned:** go back to Phase 4 and assign skills. Ask the user
    which skills the agent needs for its step.
  - **Skill not found:** create via `/create-skill-mc`, re-fetch skills catalog
    (`/api/specs/skills`), then re-run the audit.
  - **Provider mismatch:** ask the user whether to add provider support to the
    skill or choose an alternative.
  - **Capability gap:** identify which skill would fill the gap — reuse from
    the skills catalog or create a new one.
  - **Missing reviewSpecId:** select a real ID from `availableReviewSpecs`. If
    none is suitable, create a new review spec using the procedure in Phase 5
    ("Creating a Review Spec"), then re-fetch context and use the new ID.
  - **Missing onReject:** define the routing policy — which step to return to on
    rejection (e.g., `"return_to_step:draft"`).

Do NOT proceed to publish until the audit shows zero issues. Re-run the audit
after every resolution to confirm the fix.

After all issues are resolved, re-fetch both context and skills one final time:

```bash
curl -s http://localhost:3000/api/specs/squad/context
curl -s http://localhost:3000/api/specs/skills
```

Confirm all agent skills appear in the skills catalog and all review spec IDs
are valid in `availableReviewSpecs` before moving on.

## Phase 7: Review and Publish

Before publish, present a final summary with:

- squad metadata
- required capabilities
- required and optional skills
- any new skills created in this flow
- roster
- workflow
- exit criteria
- review policy

Do not ask for approval to publish until this final summary has been shown in
full.

Use this format:

```text
═══════════════════════════════════════
  Squad Blueprint Summary
═══════════════════════════════════════
Squad: {displayName}
Name: {name}
Description: {description}
Outcome: {outcome}

Capabilities:
  - ...

Skills:
  - available: ...
  - created now: ...

Agents ({count}):
  [{key}] {name} | {displayName}
    role: {role}
    model: {model}
    skills: {skills or "(none)"}
    soul: {soulPreview}

Workflow: {workflowName}
  1. [{stepKey}] {type}:{agentKey} - {title}

Exit Criteria: {exitCriteria}
Review Policy: {reviewPolicy}
═══════════════════════════════════════
```

The roster section must list each agent's skills explicitly, one agent at a
time, even when the list is empty or the agent is reused.

On approval, publish with:

```bash
curl -s -X POST http://localhost:3000/api/specs/squad \
  -H "Content-Type: application/json" \
  -d '{
    "squad": {
      "name": "...",
      "displayName": "...",
      "description": "...",
      "outcome": "..."
    },
    "agents": [
      {
        "key": "...",
        "name": "...",
        "displayName": "...",
        "role": "...",
        "prompt": "...",
        "model": "...",
        "skills": ["..."],
        "soul": "...",
        "reuseName": "..."
      }
    ],
    "workflows": [
      {
        "key": "...",
        "name": "...",
        "steps": [
          {
            "key": "...",
            "type": "agent",
            "agentKey": "...",
            "title": "...",
            "dependsOn": ["..."]
          }
        ],
        "exitCriteria": "..."
      }
    ],
    "reviewPolicy": "..."
  }'
```

Success response:

```json
{"success": true, "squadId": "..."}
```

Report the created squad ID and any follow-up recommendation, such as testing the squad or editing the generated skills.

## Contract Rules

These rules are enforced by the validator — violating them causes a publish
failure. Do not attempt to publish without satisfying every rule.

### Agent fields for new agents

Required:
- `name`
- `role`
- `prompt`
- `model`
- `skills` (array — may be empty `[]` but must be explicit)
- `soul`

Optional:
- `displayName` (UI generates initials from name slug if omitted)

### Workflow step rules

- `agent` and `review` steps must reference a valid `agentKey`
- `review` steps **must** include `reviewSpecId` — a real ID from
  `availableReviewSpecs`, never a fabricated string
- `review` steps **must** include `onReject` — the routing policy on rejection

A `review` step without `reviewSpecId` or `onReject` will be rejected by the
validator with:

```
Error: Review step "{key}" requires reviewSpecId
```

Example of a valid review step in the publish payload:

```json
{
  "key": "review",
  "type": "review",
  "agentKey": "reviewer",
  "title": "Review the draft",
  "reviewSpecId": "k57a2dz1h3m9q0v7w8x6y5z4a1b2c3d4",
  "onReject": "return_to_step:draft",
  "dependsOn": ["draft"]
}
```

### Pre-publish checklist

Before building the publish payload, verify:

1. Every agent has all required fields: `name`, `role`, `prompt`, `model`, `skills`, `soul`
2. Every `review` step has `reviewSpecId` (from `availableReviewSpecs`) and `onReject`
3. Every `agent`/`review` step references a valid `agentKey` from the roster
4. Phase 6 audit passed with zero issues

Publish is the last step. Never publish a squad that still has unresolved skill
gaps or missing required fields.
