# Story 17.3: Unified Conversation Services

Status: ready-for-dev

## Story

As a **maintainer**,
I want mentions, plan-chat, ask-user and direct thread replies built on the same conversation services,
so that message behavior is consistent.

## Acceptance Criteria

### AC1: ConversationIntentResolver

**Given** different message types are handled by different code paths
**When** the unification is complete
**Then** `mc/services/conversation_intent.py` contains a ConversationIntentResolver that classifies incoming thread messages into intents:
- `comment` -- plain comment, no agent action
- `mention` -- @mention of an agent
- `follow_up` -- non-mention follow-up to agent in active task
- `plan_chat` -- plan discussion/negotiation
- `manual_reply` -- human reply in manual/human task
**And** the resolver uses message content, task state, and thread context to determine intent

### AC2: ConversationService

**Given** mention handling, thread replies, plan-chat, and ask-user routing are separate code paths
**When** the ConversationService is created
**Then** `mc/services/conversation.py` contains a ConversationService with:
- Unified message classification (delegates to IntentResolver)
- Shared context assembly for all conversation types
- Shared response posting for all conversation types
**And** all conversation code paths go through this service

### AC3: Unified Prompt/Context Construction

**Given** mentions, ask-user, and direct replies build context differently
**When** the unification is complete
**Then** prompt and context construction for all conversation types uses the same ThreadContextBuilder (from 16.1)
**And** the only differences are parameterized (e.g., mention includes mention metadata, plan-chat includes plan context)

### AC4: Mention Behavior Preserved

**Given** mentions have specific behavior: they do NOT change task status
**When** the unification is complete
**Then** mention behavior is preserved exactly:
- Mentions trigger agent response but don't move status
- Non-mention follow-ups CAN move status (if task is in appropriate state)
- Universal mentions work across all statuses
**And** all mention-related tests pass

### AC5: Known Issue Fixed -- Direct Replies to CC Tasks

**Given** there is a known issue with direct replies for Claude Code tasks
**When** this story is complete
**Then** direct thread replies to Claude Code tasks work correctly
**And** the fix is part of the unified ConversationService

### AC6: Test Coverage

**Given** the new conversation services
**When** tests are written
**Then** they cover:
- Intent resolution for each intent type
- Mention handling (status preserved)
- Follow-up handling (status can change)
- Plan-chat routing
- Ask-user routing
- Manual task replies
- Direct reply to CC tasks (the fixed issue)
**And** all existing tests pass

## Tasks / Subtasks

- [ ] **Task 1: Analyze current conversation code paths** (AC: #1, #2)
  - [ ] 1.1 Read `mc/mentions/handler.py` completely
  - [ ] 1.2 Read `mc/mentions/watcher.py` completely
  - [ ] 1.3 Read `mc/chat_handler.py` completely
  - [ ] 1.4 Read `mc/ask_user/handler.py` completely
  - [ ] 1.5 Read `mc/plan_negotiator.py` -- plan chat logic
  - [ ] 1.6 Document: shared patterns, divergent paths, the CC direct reply issue

- [ ] **Task 2: Create ConversationIntentResolver** (AC: #1)
  - [ ] 2.1 Create `mc/services/conversation_intent.py` with ConversationIntentResolver
  - [ ] 2.2 Implement intent classification logic
  - [ ] 2.3 Write tests in `tests/mc/services/test_conversation_intent.py`

- [ ] **Task 3: Create ConversationService** (AC: #2, #3)
  - [ ] 3.1 Create `mc/services/conversation.py` with ConversationService
  - [ ] 3.2 Implement unified message classification (delegates to IntentResolver)
  - [ ] 3.3 Implement shared context assembly
  - [ ] 3.4 Implement shared response posting
  - [ ] 3.5 Write tests in `tests/mc/services/test_conversation.py`

- [ ] **Task 4: Migrate mention handling** (AC: #4)
  - [ ] 4.1 Update `mc/mentions/handler.py` to delegate to ConversationService
  - [ ] 4.2 Preserve mention-specific behavior (no status change)
  - [ ] 4.3 Preserve universal mention behavior
  - [ ] 4.4 Run mention-related tests

- [ ] **Task 5: Migrate plan-chat, ask-user, and direct replies** (AC: #2, #5)
  - [ ] 5.1 Update plan-chat to use ConversationService
  - [ ] 5.2 Update ask-user routing to use ConversationService
  - [ ] 5.3 Fix direct reply to CC tasks as part of unified service
  - [ ] 5.4 Write tests for the CC direct reply fix

- [ ] **Task 6: Final verification** (AC: #6)
  - [ ] 6.1 Run full test suite
  - [ ] 6.2 Run linter
  - [ ] 6.3 Verify mention tests, plan-chat tests, ask-user tests all pass

## Dev Notes

### Architecture Patterns

**Intent-Based Routing:** Instead of routing by code path (mention handler vs chat handler vs ask-user handler), all messages flow through ConversationService which resolves intent first, then routes. This ensures consistent behavior.

**ThreadInput Semantics in Backend:** The intents map to what the frontend will later expose as ThreadInput types: comment, mention, follow_up, plan_chat, manual_reply.

**UX NOT CHANGED:** This story consolidates the internal contract. No UX changes. The user sees the same behavior.

**Key Files to Read First:**
- `mc/mentions/handler.py` -- mention handling
- `mc/mentions/watcher.py` -- mention detection
- `mc/chat_handler.py` -- general chat handling
- `mc/ask_user/handler.py` -- ask-user flow
- `mc/plan_negotiator.py` -- plan negotiation chat
- `mc/thread_context.py` -- thread context builder

### Project Structure Notes

**Files to CREATE:**
- `mc/services/conversation_intent.py`
- `mc/services/conversation.py`
- `tests/mc/services/test_conversation_intent.py`
- `tests/mc/services/test_conversation.py`

**Files to MODIFY:**
- `mc/mentions/handler.py` -- delegate to ConversationService
- `mc/chat_handler.py` -- delegate to ConversationService
- `mc/ask_user/handler.py` -- delegate to ConversationService
- `mc/plan_negotiator.py` -- may need adjustment

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log
