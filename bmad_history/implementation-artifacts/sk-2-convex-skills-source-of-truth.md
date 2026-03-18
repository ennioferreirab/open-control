# Story SK.2: Convex as Source of Truth for Agent Skills at Dispatch

Status: ready-for-dev

## Story

As an agent operator,
I want skills edited in the dashboard (Convex) to be used at agent dispatch time,
so that I can manage agent skills from the UI without editing YAML files.

## Acceptance Criteria

1. In `mc/executor.py` `_execute_task()`, after existing Convex model/prompt sync, agent skills are overridden from Convex if present
2. In `mc/step_dispatcher.py` nanobot dispatch path, after prompt sync inside `if convex_agent:` block, skills are overridden from Convex
3. In `mc/step_dispatcher.py` CC dispatch path, inside `if convex_agent_raw:` block, skills are overridden from Convex
4. Override only happens when `convex_agent.get("skills")` returns a non-None value
5. Logging indicates when skills are synced from Convex vs YAML
6. Unit tests verify Convex override behavior for each path

## Tasks / Subtasks

- [ ] Task 1: Add Convex skills override in `mc/executor.py` `_execute_task()` (AC: #1, #4, #5)
  - [ ] After the existing prompt sync block (around line 1008), add skills sync
  - [ ] Pattern: `convex_skills = convex_agent.get("skills"); if convex_skills is not None: agent_skills = convex_skills`
  - [ ] Add logging when skills differ from YAML
- [ ] Task 2: Add Convex skills override in `mc/step_dispatcher.py` nanobot path (AC: #2, #4, #5)
  - [ ] Inside the `if convex_agent:` block (around line 368), after prompt sync
  - [ ] Same pattern as executor: override agent_skills from Convex if present
  - [ ] Add logging when skills differ from YAML
- [ ] Task 3: Add Convex skills override in `mc/step_dispatcher.py` CC path (AC: #3, #4, #5)
  - [ ] Inside `if convex_agent_raw:` block (around line 555), add skills override
  - [ ] Pattern: `convex_skills = convex_agent_raw.get("skills"); if convex_skills is not None: agent_data_for_cc.skills = convex_skills`
  - [ ] Add logging when skills differ
- [ ] Task 4: Write tests (AC: #6)
  - [ ] Test executor: Convex skills override when present
  - [ ] Test executor: YAML skills kept when Convex returns None
  - [ ] Test step_dispatcher nanobot path: Convex skills override
  - [ ] Test step_dispatcher CC path: Convex skills override on agent_data_for_cc

## Dev Notes

### Architecture & Implementation Details

**Pattern to follow** — identical to existing model/prompt sync. The code already fetches `convex_agent` via `self._bridge.get_agent_by_name(agent_name)` and overrides model/prompt. Skills follow the same pattern.

**mc/executor.py `_execute_task()`** (line ~975-1034):
- `convex_agent` is fetched at line 978
- Model sync: lines 981-997
- Prompt sync: lines 999-1008
- ADD skills sync right after prompt sync (around line 1008-1009):
```python
# Sync skills from Convex (same pattern as prompt/model)
convex_skills = convex_agent.get("skills")
if convex_skills is not None:
    if convex_skills != agent_skills:
        logger.info(
            "[executor] Skills synced from Convex for '%s': %s -> %s",
            agent_name, agent_skills, convex_skills,
        )
    agent_skills = convex_skills
```

**mc/step_dispatcher.py nanobot path** (line ~362-400):
- `convex_agent` is fetched at line 365-367
- Prompt sync: lines 369-377
- ADD skills sync after prompt sync (around line 377-378):
```python
convex_skills = convex_agent.get("skills")
if convex_skills is not None:
    if convex_skills != agent_skills:
        logger.info(
            "[dispatcher] Skills synced from Convex for '%s': %s -> %s",
            agent_name, agent_skills, convex_skills,
        )
    agent_skills = convex_skills
```

**mc/step_dispatcher.py CC path** (line ~550-569):
- `convex_agent_raw` is fetched at line 552-554
- Inside the `if convex_agent_raw:` block (line 555):
- After line 557 (role enrichment), add:
```python
convex_skills = convex_agent_raw.get("skills")
if convex_skills is not None:
    agent_data_for_cc.skills = convex_skills
```

### Key Constraints

- `agent_skills` is a `list[str]` — Convex stores it as `v.array(v.string())`
- Only override when value is not None (empty list `[]` IS a valid override meaning "no skills")
- The `convex_agent` dict comes from `bridge.get_agent_by_name()` which returns the raw Convex document

### Project Structure Notes

- Tests go in `tests/mc/`
- Use `uv run pytest` to run tests
- Existing test patterns in `tests/mc/test_executor.py` and `tests/mc/test_step_dispatcher.py` can be extended

### References

- [Source: mc/executor.py#_execute_task (lines 960-1034) — Convex model/prompt sync pattern]
- [Source: mc/step_dispatcher.py (lines 362-400) — nanobot dispatch Convex override]
- [Source: mc/step_dispatcher.py (lines 550-569) — CC dispatch Convex enrichment]
- [Source: mc/types.py:327 — AgentData.skills field definition]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
