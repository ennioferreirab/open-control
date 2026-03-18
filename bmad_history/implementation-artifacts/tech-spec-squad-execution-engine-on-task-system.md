# Tech Spec: Squad Execution Engine On Task System

## Summary

Implement squad mission execution by launching a task from a `squadSpec` and `workflowSpec`, compiling the workflow into `executionPlan`, materializing it into Convex `steps`, and reusing the current MC runtime for dispatch and review.

## Problems Addressed

- squads stop at blueprint persistence
- no mission launch path exists
- workflow semantics are lost before runtime
- no workflow mission provenance exists

## Product Outcome

Users can click `Run Mission` on a squad, choose a workflow and board, and receive a real task that runs through the existing task and step system.

## Architectural Rules

- Convex owns mission state
- `tasks` and `steps` remain the runtime instance model
- Python runtime executes runnable steps; it does not own orchestration state
- board-scoped memory remains unchanged
