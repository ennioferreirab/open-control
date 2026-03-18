# Story: Skill-First Squad Authoring and Unified Skill Standard

Status: ready-for-dev

## Story

As a Mission Control operator,
I want `Create Squad` to use a single terminal-driven, skills-first architect flow,
so that squad design, skill discovery, missing-skill creation, and squad publish
all follow one consistent standard across our stack.

## Problems Found

- Squad creation still reflects two competing architectures:
  - the real terminal flow using `/create-squad-mc`
  - the old shared squad authoring path using `/api/authoring/squad-wizard`
- The current `/create-squad-mc` flow is not explicitly skills-first.
- New squad agents are not yet governed by one strong contract covering
  `prompt`, `model`, `skills`, and `soul`.
- Local skill creation is not yet aligned to Anthropic's `skill-creator`
  workflow and anatomy.
- Missing required skills are not treated as first-class authoring gaps inside
  squad creation.

## Solution

- make the terminal-driven `/create-squad-mc` flow the only real squad-authoring
  path
- remove the old squad shared-authoring route and its squad-specific contract
- redesign squad discovery around capabilities, required skills, and patterns
- require every newly created squad agent to include:
  - `prompt`
  - `model`
  - `skills`
  - `soul`
- add memorable agent display-name rules inspired by Opensquad
- study Anthropic's upstream `skill-creator` and adopt a unified local skill
  standard based on it
- update the local `skill-creator` to that unified standard
- let squad authoring create missing required skills before publish
- validate the final squad graph before publish

## Acceptance Criteria

1. `Create Squad` uses only the terminal-driven `/create-squad-mc` flow.
2. The old squad shared-authoring route is removed from active product use.
3. Squad discovery explicitly covers required capabilities, required skills, and
   relevant patterns before finalizing the roster.
4. Every newly created squad agent carries explicit `prompt`, `model`, `skills`,
   and `soul` values in the final authored payload.
5. Newly created squad agents receive memorable human-facing names following the
   approved naming convention, while persisted slugs remain safe and stable.
6. The local `skill-creator` is updated to follow a unified standard derived
   from Anthropic's `skill-creator`.
7. The implementation includes an explicit study/gap-analysis step for the
   Anthropic `skill-creator` before local adaptation.
8. When a required skill is missing, the squad authoring flow can guide the
   user through creating it before squad publish.
9. Squad publish is blocked when the final graph is missing required agent or
   skill contract data.

## Tasks / Subtasks

- [ ] Task 1: Study Anthropic's `skill-creator` and record the gap analysis
- [ ] Task 2: Remove the old squad shared-authoring path
- [ ] Task 3: Expand squad authoring context for skills-first discovery
- [ ] Task 4: Rewrite `/create-squad-mc` around skills-first discovery
- [ ] Task 5: Update the local `skill-creator` to the unified standard
- [ ] Task 6: Add squad graph validation for skills-first publish rules
- [ ] Task 7: Wire missing-skill creation into the squad flow
- [ ] Task 8: Run focused dashboard and real-flow verification

## Dev Notes

- Scope the authoring-path removal to squad creation. Do not accidentally break
  agent authoring.
- Preserve the dashboard shell that launches the terminal flow.
- Treat Anthropic upstream as the contract reference and keep local divergence
  narrow and explicit.
- Avoid touching unrelated in-progress squad detail/canvas work in the current
  worktree.

### References

- [Source: docs/plans/2026-03-16-skill-first-squad-authoring-design.md]
- [Source: docs/plans/2026-03-16-skill-first-squad-authoring-implementation-plan.md]
- [Source: /Users/ennio/.claude/skills/create-squad-mc/SKILL.md]
- [Source: /Users/ennio/.codex/skills/.system/skill-creator/SKILL.md]
- [Source: https://github.com/anthropics/skills/tree/main/skills/skill-creator]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
