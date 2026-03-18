# Tech Spec: AI Workflow Planning Bypass

## Objective

Prevent workflow-generated squad missions from entering the legacy `inbox -> planning -> lead-agent replanning` path.

## Problem

The current squad mission launch already compiles and saves a workflow-generated `executionPlan`, but the task is still treated like a generic task:

- `InboxWorker` routes it to `planning`
- `PlanningWorker` generates a new lead-agent plan
- the original workflow plan is overwritten

This breaks the core promise of squad execution, because the mission stops following the selected workflow.

## Scope

- launch-state guardrail for `ai_workflow` missions
- inbox worker bypass for workflow-generated plans
- planning worker bypass for workflow-generated plans
- regression tests proving that workflow plans are preserved

## Acceptance Signals

- an `ai_workflow` mission does not enter legacy planning once its workflow plan exists
- the original workflow-generated `executionPlan` remains intact until kickoff
- task kickoff materializes the workflow plan rather than a replanned lead-agent plan
