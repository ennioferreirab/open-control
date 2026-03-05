# Story SK.1: Startup Skill Distribution + MC Skills Directory

Status: ready-for-dev

## Story

As a system administrator,
I want builtin skills to be automatically distributed to the workspace at startup,
so that all agents can discover and use them without manual setup.

## Acceptance Criteria

1. A new `mc/skills/` directory exists with `__init__.py` exposing `MC_SKILLS_DIR` path constant and a `README.md`
2. `sync_skills()` in `mc/gateway.py` calls `_distribute_builtin_skills()` before existing sync logic
3. `_distribute_builtin_skills()` copies skill directories (those with SKILL.md) from source dirs to `~/.nanobot/workspace/skills/` if they don't already exist there
4. Existing workspace skills are NEVER overwritten (preserves user customizations)
5. Both nanobot vendor builtins and mc builtins are distributed
6. Distribution is logged with skill name
7. Unit tests validate copy-new, skip-existing, and skip-non-skill-dir behaviors

## Tasks / Subtasks

- [ ] Task 1: Create `mc/skills/` directory (AC: #1)
  - [ ] Create `mc/skills/__init__.py` with `MC_SKILLS_DIR = Path(__file__).parent`
  - [ ] Create `mc/skills/README.md` explaining MC skills vs nanobot vendor skills
- [ ] Task 2: Add `_distribute_builtin_skills()` helper to `mc/gateway.py` (AC: #2, #3, #4, #5, #6)
  - [ ] Add the helper function that takes workspace_skills_dir and *source_dirs
  - [ ] For each source_dir, iterate subdirectories that contain SKILL.md
  - [ ] Skip if target already exists in workspace (never overwrite)
  - [ ] Use `shutil.copytree()` to copy new skills
  - [ ] Log each distributed skill
- [ ] Task 3: Integrate `_distribute_builtin_skills()` into `sync_skills()` (AC: #2, #5)
  - [ ] Import `MC_SKILLS_DIR` from `mc.skills`
  - [ ] Resolve nanobot builtin skills dir (already available as `default_dir`)
  - [ ] Resolve workspace skills dir from config
  - [ ] Call `_distribute_builtin_skills(workspace_skills_dir, nanobot_builtin_dir, mc_skills_dir)` before existing SkillsLoader sync
- [ ] Task 4: Write tests in `tests/mc/test_skill_distribution.py` (AC: #7)
  - [ ] Test: copies new skill dir with SKILL.md to workspace
  - [ ] Test: skips existing workspace skill (never overwrites)
  - [ ] Test: skips directory without SKILL.md
  - [ ] Test: creates workspace skills dir if missing
  - [ ] Test: handles missing source dirs gracefully

## Dev Notes

### Architecture & Implementation Details

**File: `mc/gateway.py`** — line 634 is `sync_skills()`. `shutil` is already imported at line 17.

The helper function signature:
```python
def _distribute_builtin_skills(workspace_skills_dir: Path, *source_dirs: Path) -> None:
```

**Integration point** — inside `sync_skills()`, BEFORE the existing `SkillsLoader` discovery (line 655). The distribution step copies files to workspace so that the subsequent SkillsLoader discovery finds everything in one place.

**Nanobot builtin dir**: `vendor/nanobot/nanobot/skills/` — accessed via `default_dir` which is already resolved at line 649 from `skills_mod.BUILTIN_SKILLS_DIR`.

**Workspace dir**: Use `load_config().workspace_path / "skills"` — the workspace path is already loaded at line 654.

**MC skills dir**: Import from `mc.skills.MC_SKILLS_DIR`. Currently empty (no SKILL.md subdirs), but the distribution loop handles this gracefully.

### Project Structure Notes

- `mc/` is 100% our code, NOT vendor
- `vendor/nanobot/` is upstream subtree — DO NOT modify
- Tests go in `tests/mc/`
- Use `uv run pytest` to run tests

### References

- [Source: mc/gateway.py#sync_skills (line 634-708)]
- [Source: mc/gateway.py imports (line 17 — shutil already imported)]
- [Source: vendor/nanobot/nanobot/skills/ — builtin skills with SKILL.md files]

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
