# Tech Spec: Squad Mission Launch And Task Binding

## Objective

Add the missing entrypoint that launches a mission from a published squad into the Convex task system.

## Scope

- `Run Mission` UI from squad detail
- board and workflow selection
- task creation with `workMode = ai_workflow`
- binding of `squadSpecId` and `workflowSpecId`

## Acceptance Signals

- launch returns a task id
- the created task is board-bound
- the task is visibly tied to the selected squad and workflow
