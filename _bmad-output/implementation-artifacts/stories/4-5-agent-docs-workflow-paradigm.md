# Story: Update Agent Docs for Workflow-First Paradigm

## Story
As a developer or AI agent working on the project, I need the agent docs to reflect the new workflow-first creation paradigm, so that contracts and architecture docs are accurate and up to date.

## Status: ready-for-dev

## Context
The project has shifted from a squad-centric creation model (where workflows were only created as part of squad publish) to a workflow-first model where workflows can be created independently and linked to existing squads. Three agent docs need updating: `service_architecture.md`, `harness_engineering.md`, and `database_schema.md`.

## Acceptance Criteria
- [ ] `service_architecture.md` documents the workflow-first creation paradigm
- [ ] `service_architecture.md` explains the conceptual model: Squad = agent roster, Workflow = execution plan
- [ ] `harness_engineering.md` documents the `/create-workflow-mc` skill and its relationship to `/create-squad-mc`
- [ ] `database_schema.md` documents the `publishStandalone` mutation as an alternative workflow creation path
- [ ] `database_schema.md` documents the `/api/specs/workflow/context` and `/api/specs/workflow` endpoints
- [ ] All existing correct information is preserved — only additions and corrections
- [ ] `make lint && make typecheck` passes (docs-only changes won't affect this, but verify)

## Tasks

- [ ] **Update `agent_docs/service_architecture.md`**
  - Find the section that describes squad/workflow creation (or the task execution section)
  - Add a subsection: "Workflow-First Creation Paradigm"
  - Document:
    - **Conceptual model:** Squad = reusable agent roster (team composition). Workflow = execution plan that references a squad's agents to define step sequences.
    - **Two creation paths:**
      1. **Squad-first (existing):** `/create-squad-mc` creates squad + agents + workflows atomically via `squadSpecs:publishGraph`
      2. **Workflow-first (new):** `/create-workflow-mc` selects an existing squad and creates a standalone workflow via `workflowSpecs:publishStandalone`
    - **Squad agent reuse emphasis:** When creating squads, the skill enforces a Reuse Assessment — existing agents are preferred over new ones
    - **Data flow:** `workflowSpecs.squadSpecId` links every workflow to its parent squad. Workflows reference squad agents by name (resolved to agentId at publish time).

- [ ] **Update `agent_docs/harness_engineering.md`**
  - Find the skill registration section (or the section listing MC skills)
  - Add entry for `/create-workflow-mc`:
    - Purpose: workflow-focused creation skill (4 phases: Intent & Squad Selection, Agent Roster Review, Step Design, Review & Publish)
    - Relationship to `/create-squad-mc`: can invoke it inline when user needs a new squad
    - API dependencies: `GET /api/specs/workflow/context`, `POST /api/specs/workflow`
  - Update the `/create-squad-mc` entry (if it exists) to note the agent reuse emphasis in Phase 4

- [ ] **Update `agent_docs/database_schema.md`**
  - Find the `workflowSpecs` table section
  - Add documentation for the new mutation `workflowSpecs:publishStandalone`:
    - Purpose: create a published workflowSpec linked to an existing squad (standalone, not through squad graph)
    - Args: `squadSpecId`, `workflow { name, steps[], exitCriteria? }`
    - Validation: squad must be published, agentKeys must resolve to squad's agents, review steps validated
  - Add the new API endpoints under the appropriate section:
    - `GET /api/specs/workflow/context` — returns published squads with agents, existing workflows, review specs, models
    - `POST /api/specs/workflow` — publishes a standalone workflow via `publishStandalone`
  - Note: existing `squadSpecs:publishGraph` path remains the primary way to create squads with their default workflow

## File List
- `agent_docs/service_architecture.md` (modify)
- `agent_docs/harness_engineering.md` (modify)
- `agent_docs/database_schema.md` (modify)

## Dev Notes
- **Read each doc fully before editing** — these are structural contracts per CLAUDE.md. Preserve all existing correct information.
- **Keep changes additive** — we're documenting a new creation path, not replacing the existing one. The `squadSpecs:publishGraph` path still works and is used by `/create-squad-mc`.
- **Concise additions** — these docs are contracts for AI agents. Be precise and factual, not verbose. Follow the existing documentation style in each file.
- **If a relevant section doesn't exist** in the doc, create it in the most logical location following the doc's existing structure.

## Testing Standards
- Review each modified doc for accuracy against the actual implementation
- Verify no existing correct information was accidentally removed or altered

## Dev Agent Record
- Model: (to be filled by dev agent)
- Completion notes: (to be filled by dev agent)
- Files modified: (to be filled by dev agent)
