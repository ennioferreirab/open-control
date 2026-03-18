# Tech Spec: Workflow Spec Materialization To Task Steps

## Objective

Compile `workflowSpecs` into execution plans that the existing task pipeline can materialize into steps without losing workflow semantics.

## Scope

- workflow compiler
- plan source metadata
- enriched step payloads
- dependency fidelity

## Acceptance Signals

- compiled workflow plans are visible in task detail
- materialized steps preserve workflow metadata
- dependency and ordering semantics stay correct
