# Epic 4: Workflow-First Creation System — Wave Plan

## Overview
Shift creation model from squad-centric to workflow-first. Workflows become the primary entry point; squads provide the agent roster.

## Wave 1 — Backend Infrastructure (parallel)
| Story | Description | Dependencies |
|-------|-------------|--------------|
| 4-1 | Convex mutation `publishStandalone` + API endpoints (`GET context`, `POST publish`) | none |
| 4-3 | Update `/create-squad-mc` skill — agent reuse emphasis | none |

**Gate:** API endpoints respond correctly (curl test).

## Wave 2 — Skills + UI (parallel, depends on Wave 1)
| Story | Description | Dependencies |
|-------|-------------|--------------|
| 4-2 | New `/create-workflow-mc` skill (4 phases) | 4-1 (needs API endpoints) |
| 4-4 | UI: `WorkflowAuthoringWizard` + `CreateAuthoringDialog` + `AgentSidebar` wiring | 4-2 (needs skill to exist) |
| 4-5 | Update `agent_docs` for workflow-first paradigm | 4-1 (needs final mutation/endpoint signatures) |

**Gate:** `make lint && make typecheck` passes. Manual test: Create Workflow flow works end-to-end.

## Execution Notes
- Stories 4-1 and 4-3 are fully independent — run in parallel
- Story 4-2 needs 4-1's endpoints to exist but can be written before they're live (skill is a markdown file)
- Story 4-4 needs the skill name `/create-workflow-mc` but not the skill content
- Story 4-5 should be written last so docs reflect final implementation
- All stories are self-contained for Sonnet subagent delegation
