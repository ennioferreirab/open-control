# Tech Spec: LLM-First Authoring Remediation

Status: ready-for-dev

## Story

As a Mission Control builder,
I want agent and squad creation to be driven by an architect-style LLM flow,
so that the system asks coherent questions, builds structured drafts
dynamically, and persists complete blueprints instead of shallow shells.

## Problems Found

The current implementation has four structural problems:

1. `Create Agent` and `Create Squad` are still primarily manual, form-first
   flows in the UI.
2. `Create Squad` persists only the squad shell and drops child entities such as
   agents and workflows.
3. The squad authoring backend is too shallow and stores phase text instead of a
   structured graph.
4. UI phase names and backend phase names do not align cleanly, which makes the
   flow brittle and difficult to evolve.

These problems explain the observed failure mode:

- the user completes the squad wizard
- the saved squad shows outcome text
- agents and workflows remain empty

## Goals

1. Replace manual phase-form primary flows with chat-first, LLM-first authoring.
2. Use one shared authoring engine for both agent and squad creation.
3. Keep a live structured preview while the LLM conversation evolves.
4. Persist a full squad blueprint graph:
   - `squadSpec`
   - `agentSpecs`
   - `workflowSpecs`
   - optional `reviewSpecs`
5. Preserve the existing runtime, Kanban model, and board-scoped memory.

## Non-Goals

- No rewrite of the runtime executor
- No `Run Squad` execution in this remediation program
- No giant workflow engine
- No continued investment in form-first primary creation UX

## Architecture

### Shared authoring engine

A single authoring engine should:

- track conversation history
- maintain a structured draft graph
- compute unresolved gaps
- choose the next question
- decide when the draft is ready for approval

### Chat-first shells

Both create flows should use:

- chat on the main pane
- live preview on the side
- manual editing only as a secondary path

### Draft graph

The squad draft must be a graph, not flat strings:

- squad metadata
- proposed agents
- proposed workflows
- review policy
- unresolved questions

### Publish orchestration

Publishing a squad must persist the full graph, not only a squad shell.

## Story Sequence

### Wave 1: Shared Authoring Engine and Draft Graph Foundation

Build the shared authoring session contract, unify phase semantics, and replace
flat squad phase strings with structured graph patches.

### Wave 2: Chat-First Create Agent

Replace the current manual agent flow with an architect-style chat flow backed
by the shared authoring engine.

### Wave 3: Chat-First Create Squad and Graph Persistence

Replace the current manual squad flow with an architect-style chat flow and
persist the full blueprint graph correctly.

### Wave 4: Stabilization, Validation, and Rollout Gates

Validate the new flows against the real bug, confirm persisted records match the
preview, and document the remaining follow-up boundary.

## Success Metrics

- Agent creation is LLM-first in the real UI, not just on the backend
- Squad creation is LLM-first in the real UI, not just on the backend
- Persisted squads show real agent and workflow counts
- Previewed squad structure matches persisted records
- No regression to Kanban or board-scoped memory behavior

## Key Risks and Guardrails

- Do not keep expanding the manual wizard as the main path
- Do not let the UI publish partial squad records
- Do not keep a phase model mismatch between frontend and backend
- Do not validate only against `npm run dev`; use the full `uv run nanobot mc start` stack

## References

- [Source: docs/plans/2026-03-14-llm-first-authoring-remediation-plan.md]
- [Source: dashboard/features/agents/components/SquadAuthoringWizard.tsx]
- [Source: dashboard/features/agents/hooks/useCreateSquadDraft.ts]
- [Source: dashboard/features/agents/components/AgentAuthoringWizard.tsx]
- [Source: mc/contexts/agents/authoring_assist.py]
- [Source: https://github.com/renatoasse/opensquad]

