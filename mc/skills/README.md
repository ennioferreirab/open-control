# MC Skills

This directory contains **Mission Control builtin skills** — skills maintained
as part of the MC codebase (mc-owned).

## How It Works

At startup, `sync_skills()` in `mc/gateway.py` calls
`_distribute_builtin_skills()` which copies skill directories from here (and
from mc/infrastructure/builtin_skills) into the workspace (`~/.open-control/workspace/skills/`).

A subdirectory is recognized as a skill if it contains a `SKILL.md` file.

## Key Rules

- **Never overwrite**: If a skill already exists in the workspace, it is
  skipped. This preserves user customizations.
- **Add new skills**: To add an MC-specific skill, create a subdirectory here
  with a `SKILL.md` file (and any supporting files). It will be distributed
  automatically on next startup.

## MC Skills vs Vendor Skills

| Aspect        | MC Skills (`mc/skills/`)                    | Builtin Skills (`mc/infrastructure/builtin_skills/`) |
|---------------|---------------------------------------------|--------------------------------------------------|
| Maintained by | This project (Mission Control)              | Upstream nanobot                                 |
| Updated via   | Normal commits                              | `git subtree pull`                               |
| Distribution  | Copied to workspace at startup              | Copied to workspace at startup                   |
