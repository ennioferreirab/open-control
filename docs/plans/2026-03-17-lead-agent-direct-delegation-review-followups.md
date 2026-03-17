# Lead-Agent Direct Delegation Review Follow-Ups

**Goal:** Convert the review findings from March 17, 2026 into a small,
implementation-ready follow-up batch that restores the intended task-routing
contract without reopening the planning ambiguity that this refactor removed.

## Stories

1. `31.8` Preserve human routing and explicit agent ownership
2. `31.9` Fail safe when direct delegation has no valid candidate
3. `31.10` Filter non-delegatable agents from active registry
4. `31.11` Move step metrics to canonical workflow completion
5. `31.12` Restore legacy workflow compatibility for missing `workMode`

## Recommended Waves

### Wave 0: Routing Truth

**Stories:** `31.10` -> `31.8` -> `31.9`

**Objective:**
- freeze who is actually delegatable
- restore the `human` routing contract
- make no-candidate behavior explicit and operator-visible

**Why this order:**
- `31.10` narrows the roster that all routing decisions depend on
- `31.8` restores the operator-directed bypass before touching failure handling
- `31.9` can then define safe failure semantics against the correct candidate
  set

### Wave 1: Secondary Corrections

**Stories:** `31.11` and `31.12` in parallel

**Objective:**
- repair missing lifecycle metrics
- restore compatibility for legacy workflow tasks

**Why these can run in parallel:**
- `31.11` lives in step/task lifecycle plumbing
- `31.12` lives in workflow detection, read models, and legacy data handling
- they share conceptual context but have largely disjoint write scopes

## Points of Attention

1. `routingMode="human"` is authoritative operator intent. The runtime should
   not add fake lead-agent metadata or silently substitute another agent.
2. A direct-delegate task with no candidate must never re-enter planning. The
   failure path should be visible, recoverable, and based on existing lifecycle
   semantics where possible.
3. Delegatability needs an explicit rule. Filtering only on `isSystem` or
   `enabled` is too weak and will drift again as new runtime-only agent roles
   appear.
4. Metric updates must happen exactly once at lifecycle truth. Manual UI paths
   can still exist, but they should not be the canonical source of counters.
5. Legacy workflow compatibility should use durable workflow evidence, not broad
   heuristics that might misclassify old direct tasks.
6. Add boundary tests that cross Python routing decisions and Convex document
   state. The current targeted suites pass while still missing these contract
   breaks.

## Practical Recommendation

If the goal is to stabilize quickly on `main`, implement Wave 0 first and do
not parallelize it. Only after routing truth is restored should Wave 1 proceed
in parallel.
