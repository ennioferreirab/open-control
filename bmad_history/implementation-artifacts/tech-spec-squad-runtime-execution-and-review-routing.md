# Tech Spec: Squad Runtime Execution And Review Routing

## Objective

Make launched squad missions behave correctly in runtime by using the current dispatcher and lifecycle system with workflow-aware metadata and thin workflow-run provenance.

## Scope

- `workflowRuns`
- dispatch of agent steps
- checkpoint and human-step pausing
- review-step routing groundwork

## Acceptance Signals

- agent steps dispatch through the current runtime
- human/checkpoint steps pause coherently
- workflow provenance is inspectable from the mission task
