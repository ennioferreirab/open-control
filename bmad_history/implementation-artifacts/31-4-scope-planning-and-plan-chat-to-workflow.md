# Story 31.4: Scope Planning and Plan Chat to Workflow

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want planning and plan-negotiation semantics to apply only to workflow-backed
tasks,
so that direct-delegate and human-routed tasks behave like normal task threads.

## Overall Objective

Restrict planning ownership and `plan_chat` intent so non-workflow tasks can no
longer enter lead-agent plan negotiation or plan-review flows.

## Acceptance Criteria

1. `plan_chat` intent is returned only for workflow-backed tasks.
2. Direct-delegate tasks use normal comment or follow-up behavior instead of
   plan negotiation.
3. Human-routed tasks do not enter plan negotiation.
4. Planning-worker logic no longer treats non-workflow tasks as eligible for
   lead-agent plan generation.
5. Focused tests prove the new conversation and runtime boundary.

## Files To Change

- `mc/contexts/conversation/intent.py`
- `mc/contexts/conversation/service.py`
- `mc/contexts/planning/negotiation.py`
- `mc/runtime/workers/planning.py`
- `tests/mc/services/test_conversation_intent.py`
- `tests/mc/services/test_conversation.py`

## Tasks / Subtasks

- [ ] Task 1: Rework negotiable-status checks
  - [ ] 1.1 Make workflow ownership part of the gate
  - [ ] 1.2 Stop inferring negotiation eligibility from generic review state
  - [ ] 1.3 Preserve workflow review behavior

- [ ] Task 2: Restrict conversation dispatch
  - [ ] 2.1 Keep `plan_chat` for workflow tasks only
  - [ ] 2.2 Route direct-delegate task messages through normal follow-up logic
  - [ ] 2.3 Route human-routed task messages through normal thread behavior

- [ ] Task 3: Align planning runtime ownership
  - [ ] 3.1 Remove non-workflow assumptions from planning worker branches
  - [ ] 3.2 Keep workflow planning behavior intact
  - [ ] 3.3 Avoid reintroducing a generic no-plan review bootstrap

- [ ] Task 4: Add focused regression tests
  - [ ] 4.1 Extend conversation-intent tests
  - [ ] 4.2 Extend conversation-service tests
  - [ ] 4.3 Add a runtime regression proving non-workflow tasks cannot enter
        plan negotiation

## Dev Notes

- This story is not complete if any direct-delegate or human-routed task can
  still trigger `handle_plan_negotiation`.
- Keep workflow behavior unchanged except where the gate needs to become more
  explicit.

## References

- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-design.md`]
- [Source: `docs/plans/2026-03-17-lead-agent-direct-delegation-implementation-plan.md`]
