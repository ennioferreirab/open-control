# Story 21.2: Make Conversation Own Ask-User and Mentions

Status: ready-for-dev

## Story

As a **backend maintainer**,
I want `conversation` to become the only owner of ask-user and mention flows,
so that those interaction behaviors stop living behind legacy packages and compatibility bridges.

## Acceptance Criteria

### AC1: Ask-User Ownership Moved

**Given** ask-user behavior currently exists in legacy packages and compatibility bridges
**When** the migration completes
**Then** all concrete ask-user logic lives under `mc.contexts.conversation.ask_user.*`
**And** runtime, planning, and execution import only the canonical conversation paths
**And** the legacy `mc/ask_user/*` package is removed.

### AC2: Mention Ownership Moved

**Given** mention handling currently exists in legacy packages and wrappers
**When** the migration completes
**Then** all concrete mention logic lives under `mc.contexts.conversation.mentions.*`
**And** no import sites continue to use `mc.mentions.*`
**And** the legacy `mc/mentions/*` package is removed.

### AC3: Compatibility Bridges Removed

**Given** `sys.modules` aliases and wildcard re-export shims hide real ownership
**When** this story completes
**Then** those compatibility bridges are deleted instead of preserved
**And** the architecture tests reflect that the ownership transition is finished.

### AC4: Focused Backend Regression Passes

**Given** ask-user and mention behavior is used across planning, conversation, and execution
**When** the story completes
**Then** the focused backend suite for ask-user, mention, and conversation flows passes from the migration worktree.

### AC5: Wave Exit Quality Gate

**Given** this is a migration wave
**When** the story closes
**Then** `/code-review` is run on the diff
**And** Playwright smoke confirms the dashboard still loads and task/thread flows are reachable after the backend ownership move.

## Tasks / Subtasks

- [ ] **Task 1: Convert tests to canonical conversation imports** (AC: #1, #2, #3)
  - [ ] 1.1 Rewrite ask-user tests to import from `mc.contexts.conversation.ask_user.*`
  - [ ] 1.2 Rewrite mention tests to import from `mc.contexts.conversation.mentions.*`
  - [ ] 1.3 Remove any test assertions that preserve legacy aliases

- [ ] **Task 2: Move ask-user concrete behavior** (AC: #1, #3)
  - [ ] 2.1 Create canonical conversation-owned ask-user modules
  - [ ] 2.2 Move handler, registry, and watcher behavior into them
  - [ ] 2.3 Update planning, execution, and conversation import sites
  - [ ] 2.4 Delete legacy `mc/ask_user/*` modules

- [ ] **Task 3: Move mention concrete behavior** (AC: #2, #3)
  - [ ] 3.1 Create canonical conversation-owned mention modules
  - [ ] 3.2 Move handler and watcher behavior into them
  - [ ] 3.3 Update import sites in planning, conversation, and runtime-adjacent code
  - [ ] 3.4 Delete legacy `mc/mentions/*` modules

- [ ] **Task 4: Remove compatibility wrappers and harden boundaries** (AC: #3, #4)
  - [ ] 4.1 Delete `sys.modules` compatibility bridges
  - [ ] 4.2 Delete wildcard re-export wrappers under `mc.contexts.conversation`
  - [ ] 4.3 Update architecture guardrail tests for the new canonical ownership

- [ ] **Task 5: Run the wave exit gate** (AC: #4, #5)
  - [ ] 5.1 Run focused ask-user, mention, and conversation pytest targets
  - [ ] 5.2 Run backend architecture guardrail tests
  - [ ] 5.3 Run `/code-review`
  - [ ] 5.4 Run a Playwright smoke on dashboard load and task/thread reachability
  - [ ] 5.5 Commit the wave

## Dev Notes

### Architecture Patterns

- This story completes the ownership transition hinted by the current conversation wrappers. The end state is deletion, not another layer of indirection.
- Do not create new generic helper packages. Keep behavior inside `mc.contexts.conversation`.
- Update imports in `planning` and `execution` immediately rather than leaving temporary aliases for later.

### Project Structure Notes

- Canonical destination: `mc/contexts/conversation/ask_user/*` and `mc/contexts/conversation/mentions/*`
- Delete the legacy roots completely by the end of the story.
- Run all commands from `/Users/ennio/Documents/nanobot-ennio/.worktrees/architecture-convergence`.

### References

- [Source: docs/plans/2026-03-11-architecture-convergence-plan.md#Task-2-Wave-1---make-conversation-the-only-owner-of-ask-user-and-mentions]
- [Source: docs/ARCHITECTURE.md#mccontextsconversation]
- [Source: tests/mc/test_ask_user_handler.py]
- [Source: tests/mc/test_mention_handler.py]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
