# Story: Workflow Backend Infrastructure

## Story
As a skill author, I need API endpoints and a Convex mutation to create standalone workflows linked to existing squads, so that the new `/create-workflow-mc` skill can publish workflows independently of squad creation.

## Status: ready-for-dev

## Context
Currently workflows can only be created atomically through `squadSpecs:publishGraph` (squad graph publish). We need a standalone path: a Convex mutation `workflowSpecs:publishStandalone` and two Next.js API endpoints (`GET /api/specs/workflow/context` and `POST /api/specs/workflow`).

## Acceptance Criteria
- [ ] `workflowSpecs:publishStandalone` mutation creates a published workflowSpec linked to an existing squad
- [ ] Mutation validates squadSpecId exists and is published
- [ ] Mutation resolves agentKey references to agentIds from the squad's agent roster
- [ ] Mutation validates all agentKeys reference agents that belong to the selected squad
- [ ] Mutation validates review steps have `reviewSpecId` and `onReject`
- [ ] `GET /api/specs/workflow/context` returns published squads with resolved agents and existing workflows
- [ ] `GET /api/specs/workflow/context` returns available review specs and models
- [ ] `POST /api/specs/workflow` accepts squadSpecId + workflow definition and calls `publishStandalone`
- [ ] `make lint && make typecheck` passes
- [ ] Existing tests still pass

## Tasks

- [ ] **Create Convex mutation `workflowSpecs:publishStandalone`** in `dashboard/convex/workflowSpecs.ts`
  - Args: `squadSpecId: v.id("squadSpecs")`, `workflow: v.object({ name, steps[], exitCriteria? })`
  - Step 1: Load squad by `squadSpecId`, verify status is `"published"`
  - Step 2: Load all agents from squad's `agentIds` array, build `agentName -> agentId` map
  - Step 3: Validate each step's `agentKey` resolves to an agent in the map (for `agent` and `review` type steps)
  - Step 4: Validate review steps have `reviewSpecId` (verify it exists in DB) and `onReject`
  - Step 5: Transform steps: replace `agentKey` with resolved `agentId`, generate UUID for step `id` if not provided
  - Step 6: Insert workflowSpec with `squadSpecId`, `name`, transformed `steps`, `exitCriteria`, `status: "published"`, `version: 1`, `publishedAt: new Date().toISOString()`
  - Step 7: Return the new workflowSpecId
  - Reference: existing `publish` mutation in same file for pattern; `squadGraphPublisher.ts` lines 136-160 for agent resolution pattern

- [ ] **Create `GET /api/specs/workflow/context` endpoint** at `dashboard/app/api/specs/workflow/context/route.ts`
  - Follow the exact pattern of `dashboard/app/api/specs/squad/context/route.ts`
  - Use `getClient()` helper with admin auth (same as squad context)
  - Query in parallel:
    - `squadSpecs:listByStatus` with `{ status: "published" }`
    - `reviewSpecs:listByStatus` with `{ status: "published" }`
    - `settings:get` with `{ key: "connected_models" }`
  - For each squad, resolve `agentIds` by querying `agents:listByIds` (or individual `agents:getById`)
  - For each squad, query `workflowSpecs:listBySquad` to get existing workflows
  - Response shape:
    ```json
    {
      "publishedSquads": [{
        "id": "...", "name": "...", "displayName": "...", "description": "...",
        "agents": [{ "id": "...", "name": "...", "displayName": "...", "role": "..." }],
        "existingWorkflows": [{ "id": "...", "name": "...", "stepCount": 3 }]
      }],
      "availableReviewSpecs": [{ "id": "...", "name": "...", "scope": "...", "approvalThreshold": 0.8, "reviewerPolicy": "...", "rejectionRoutingPolicy": "..." }],
      "availableModels": ["claude-sonnet-4-6", "claude-opus-4-6"]
    }
    ```
  - Note: `agents:listByIds` may not exist as a public query. Check `dashboard/convex/agents.ts` — if needed, load agents individually or use the internal query.

- [ ] **Create `POST /api/specs/workflow` endpoint** at `dashboard/app/api/specs/workflow/route.ts`
  - Follow the exact pattern of `dashboard/app/api/specs/squad/route.ts`
  - Parse body: `{ squadSpecId, workflow: { name, steps[], exitCriteria? } }`
  - Validate `squadSpecId` and `workflow` are present
  - Call `convex.mutation(api.workflowSpecs.publishStandalone, { squadSpecId, workflow })`
  - Return `{ success: true, workflowSpecId }`
  - Error handling: 400 for missing fields, 500 for mutation failure

## File List
- `dashboard/convex/workflowSpecs.ts` (modify — add `publishStandalone` mutation)
- `dashboard/app/api/specs/workflow/context/route.ts` (create)
- `dashboard/app/api/specs/workflow/route.ts` (create)

## Dev Notes
- **Convex admin auth pattern:** See `dashboard/app/api/specs/squad/context/route.ts` lines 4-13 for the `getClient()` with `setAdminAuth` pattern. Replicate exactly.
- **Agent resolution:** The squad's `agentIds` field contains `Id<"agents">[]`. Load each agent doc and use `agent.name` as the key for the `agentName -> agentId` map. The skill will send `agentKey` matching the agent's `name` slug.
- **Step schema:** Match the existing `workflowSpecs` table schema in `dashboard/convex/schema.ts` lines 554-596. Each step needs: `id` (UUID string), `title`, `type`, and optional `agentId`, `reviewSpecId`, `description`, `inputs`, `outputs`, `dependsOn`, `onReject`.
- **Workflow step types validator:** Check if `workflowStepTypeValidator` exists in schema or validators. If not, use literal union: `"agent" | "human" | "checkpoint" | "review" | "system"`.
- **No backward compat needed** — pre-production project, existing data can be deleted if schema conflicts.

## Testing Standards
- Follow `agent_docs/running_tests.md` decision tree
- Unit test the mutation logic if extractable to a lib module
- Integration test via the API endpoint with curl or test client

## Dev Agent Record
- Model: (to be filled by dev agent)
- Completion notes: (to be filled by dev agent)
- Files modified: (to be filled by dev agent)
