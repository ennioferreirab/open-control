# Story: Create Workflow MC Skill

## Story
As a user, I want a `/create-workflow-mc` skill that guides me through designing a workflow for an existing squad, so I can create execution flows independently of squad creation.

## Status: ready-for-dev

## Context
The current `/create-squad-mc` skill bundles squad + agents + workflow creation into one flow. The new `/create-workflow-mc` skill provides a lighter, workflow-focused experience: select a squad, review its agents, design steps, and publish. This is the skill invoked by the `WorkflowAuthoringWizard` terminal.

## Acceptance Criteria
- [ ] Skill file exists at `mc/skills/create-workflow-mc/SKILL.md`
- [ ] Phase 1 fetches context from `GET /api/specs/workflow/context` and presents published squads
- [ ] Phase 1 allows selecting an existing squad or creating a new one inline via `/create-squad-mc`
- [ ] Phase 2 displays the selected squad's agent roster for reference
- [ ] Phase 3 guides step design using only agents from the selected squad
- [ ] Phase 3 enforces review step contracts (real reviewSpecId, onReject)
- [ ] Phase 4 shows final summary and publishes via `POST /api/specs/workflow`
- [ ] Skill uses `disable-model-invocation: true` frontmatter
- [ ] Asks 1-2 questions at a time (same interactive pattern as create-squad-mc)

## Tasks

- [ ] **Create `mc/skills/create-workflow-mc/SKILL.md`** — Full skill definition

  Frontmatter:
  ```yaml
  ---
  name: create-workflow-mc
  description: "Workflow designer for Mission Control. Use when the user wants to create a workflow, define an execution flow, or add a new workflow to an existing squad."
  disable-model-invocation: true
  ---
  ```

  **Structure (4 phases):**

  ### Load Context First
  ```bash
  curl -s http://localhost:3000/api/specs/workflow/context
  ```
  Document the expected response shape (publishedSquads with agents and existingWorkflows, availableReviewSpecs, availableModels).

  ### Phase 1: Intent & Squad Selection
  - Ask what the workflow should accomplish
  - Present published squads from context as numbered options with agent count and existing workflow count
  - User selects a squad by number/name OR says "create new"
  - If "create new": invoke `/create-squad-mc`, then refresh context:
    ```bash
    curl -s http://localhost:3000/api/specs/workflow/context
    ```
  - Collect: `workflow.name` (slug: `^[a-z0-9]+(-[a-z0-9]+)*$`), description, selected squadSpecId

  ### Phase 2: Agent Roster Review
  - Display the selected squad's agents in a table format:
    ```text
    Squad: "Content Creation" (content-creation)
    Agents available for this workflow:
      [researcher] audience-researcher | Rafa Researcher — Audience researcher
      [writer]     post-writer | Wanda Writer — Draft writer
      [reviewer]   editorial-reviewer | Rita Reviewer — Editorial reviewer
    ```
  - Map agent names to agentKeys that will be used in step references
  - Note: NO agent creation in this flow — agents belong to the squad

  ### Phase 3: Step Design
  - Design steps one by one or accept a batch proposal
  - Each step needs: `key`, `type` (agent/human/checkpoint/review/system), `agentKey` (for agent/review), `title`, `dependsOn` (optional)
  - Review steps: must use real `reviewSpecId` from `availableReviewSpecs`, must define `onReject` (step key to return to)
  - Default quality gates: reviewer for generated output, human approval for externally important output
  - Present full workflow in sequence:
    ```text
    Workflow: "content-pipeline"
      1. [research] agent:researcher — "Research the target audience"
      2. [draft]    agent:writer — "Draft the deliverable" (depends on: research)
      3. [review]   review:reviewer — "Review the draft" (review spec: brief-quality-check, depends on: draft)
      4. [approve]  human — "Approve for publish" (depends on: review)
    ```
  - Collect exit criteria

  ### Phase 4: Review & Publish
  - Show final summary:
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
  - On approval, publish:
    ```bash
    curl -s -X POST http://localhost:3000/api/specs/workflow \
      -H "Content-Type: application/json" \
      -d '{
        "squadSpecId": "...",
        "workflow": {
          "name": "...",
          "steps": [...],
          "exitCriteria": "..."
        }
      }'
    ```
  - Report created workflowSpecId

  ### Contract Rules
  - Workflow name must be a slug: `^[a-z0-9]+(-[a-z0-9]+)*$`
  - Step keys must be unique slugs
  - `agent` and `review` steps must reference a valid `agentKey` from the squad roster
  - `review` steps must include `reviewSpecId` (from `availableReviewSpecs`) and `onReject`
  - Never fabricate reviewSpecId values

## File List
- `mc/skills/create-workflow-mc/SKILL.md` (create)

## Dev Notes
- **Follow the conventions of `mc/skills/create-squad-mc/SKILL.md`** — same markdown structure, same interactive pattern (1-2 questions at a time), same frontmatter.
- **The skill does NOT create agents or skills.** It only designs workflow steps using existing squad agents.
- **Inline squad creation** delegates to `/create-squad-mc` entirely — the LLM runs through all 6 phases of that skill, then returns to workflow creation.
- **API endpoints are created by story 4-1.** This skill depends on those endpoints existing.

## Testing Standards
- Manual testing: run the skill in a terminal session and verify the full flow
- Verify publish succeeds by checking the workflow appears in squad detail sheet

## Dev Agent Record
- Model: (to be filled by dev agent)
- Completion notes: (to be filled by dev agent)
- Files modified: (to be filled by dev agent)
