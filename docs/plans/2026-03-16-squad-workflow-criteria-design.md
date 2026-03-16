# Squad Workflow Criteria Design

## Goal

Add a third workflow tab so users can inspect and edit workflow validation criteria, while keeping squad-level review policy visible and editable at the squad level instead of duplicating it inside each workflow.

## Decisions

- `Review Policy` remains a squad-level field and is rendered once near the top of `SquadDetailSheet`.
- Workflow tabs become `Workflow`, `Steps`, and `Criteria`.
- The new `Criteria` tab edits `workflow.exitCriteria` only.
- Read mode and edit mode both expose the same information. Edit mode unlocks the inputs; read mode keeps them visible and disabled.
- Publishing continues to overwrite the current published squad spec and workflow specs in place.

## UI Shape

- `SquadDetailSheet`
  - Adds a `Review Policy` panel above the workflow section.
  - Shows the value as text in read mode and as a textarea in edit mode.
- `SquadWorkflowCanvas`
  - Adds a `Criteria` tab beside `Workflow` and `Steps`.
  - Shows `Validation Criteria` for the current workflow.
  - Keeps the selected step panel below the tabs independent from the active tab.

## Data Flow

- `EditableSquadDraft.reviewPolicy` is the source of truth for the squad-level field.
- `EditableWorkflow.exitCriteria` remains the source of truth for workflow validation criteria.
- `useUpdatePublishedSquad` sends both values in `graph`.
- Convex stores `reviewPolicy` on `squadSpecs` and `exitCriteria` on each `workflowSpecs` document.

## Test Coverage

- Canvas tabs render `Criteria`.
- Criteria tab shows and edits `Validation Criteria`.
- Squad sheet shows and publishes `Review Policy`.
- Convex publish/update paths preserve `reviewPolicy`.
