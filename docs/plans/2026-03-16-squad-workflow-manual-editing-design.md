# Squad Workflow Manual Editing Design

## Summary

Allow published squads to be edited directly from the squad sheet. Users can manually change workflow metadata, add/remove/reorder steps, edit review and checkpoint settings, and publish those changes back to the current Convex spec without creating a new version.

## Decisions

| Decision | Choice |
|----------|--------|
| Persist action | `Publicar`, not `Salvar` |
| Publish target | Overwrite the current `squadSpec`/`workflowSpecs` |
| Scope of impact | Only future executions; existing tasks stay unchanged |
| Editing surface | Expanded `SquadDetailSheet` |
| Agent navigation | Clicking an agent in squad context switches to the corresponding agent view |
| Create vs edit backend path | Keep `publishGraph` for create; add a separate update mutation for published squads |

## Architecture

The current squad sheet is read-only and already has the right context: squad metadata, workflow specs, and resolved agents. The change turns that sheet into a local draft editor with a deliberate publish action.

The frontend keeps a complete editable graph in local state:

1. squad metadata
2. workflow metadata
3. step list per workflow
4. agent selection and navigation state
5. dirty/publishing/error state

The backend keeps creation and editing separate:

1. `squadSpecs.publishGraph` remains the create flow
2. a new `squadSpecs.updatePublishedGraph` mutation updates the existing squad/workflow documents
3. `workflowSpecs` are patched in place when possible so downstream references remain stable
4. removed workflows owned by the squad are deleted or archived in the same mutation

## UI Model

`SquadDetailSheet` becomes a wider sheet with two working modes:

- `Squad` view for metadata and workflow editing
- `Agent` view for the selected agent

Within `Squad` view:

- squad title/description/outcome remain visible
- a publish bar appears only when edits exist
- each workflow renders as an editable card
- each step renders as an editable row/card
- users can add, remove, and reorder steps
- per-step fields depend on the step type

When users click an agent from:

- the agent roster
- a workflow step assignment

the sheet switches to the `Agent` view for that specific agent.

## Data Model

The editable graph mirrors the Convex publish contract and extends it with stable identifiers for existing workflow docs:

- squad fields: `name`, `displayName`, `description`, `outcome`
- workflows: existing doc id when present, `key`, `name`, `exitCriteria`
- steps: `key`, `type`, `title`, `description`, `agentKey`, `reviewSpecId`, `onReject`, `dependsOn`

The publish payload always sends the full intended graph. The server validates:

- referenced agents belong to the squad graph
- `dependsOn` references existing step keys in the same workflow
- review steps with `onReject` only point to existing step keys
- `reviewSpecId` values exist when provided

## Runtime Compatibility

Workflow specs are only compiled at mission launch time. Updating a published squad must not rewrite existing tasks or workflow runs. This design keeps runtime compatibility by limiting the update to specs used for future launches.

The mutation preserves existing workflow ids whenever the edited workflow maps to an existing document, which avoids breaking default workflow bindings and board overrides.

## Testing Strategy

- Convex mutation tests for update-in-place, workflow removal, default workflow preservation, and validation failures
- `SquadDetailSheet` tests for entering edit mode, changing steps, publishing, and disabled publish states
- `AgentSidebar`/`SquadDetailSheet` tests for agent-click navigation
- Targeted lint/format/test guardrails for touched dashboard files
