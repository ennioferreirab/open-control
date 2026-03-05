# Story SK.3: Clean Up Invalid YAML Skill References

Status: review

## Story

As a system operator,
I want agent YAML configs to only reference skills that actually exist on disk,
so that startup and dispatch don't produce "Skill not found" warnings.

## Acceptance Criteria

1. `~/.nanobot/agents/youtube-summarizer/config.yaml` skills list contains only existing skills: `youtube-watcher`, `cron`, `memory`, `summarize`
2. `~/.nanobot/agents/image-creator-agent/config.yaml` skills list contains only existing skills (remove non-existent ones like `image-generation`, `design-guidelines`, `creative-prompting`, `color-theory`, `visual-composition`, `creative-direction`; keep `skill-creator`)
3. `~/.nanobot/agents/lead-agent/config.yaml` skills list contains only existing skills (remove non-existent `orchestration`, `planning`, `task-routing`, `delegation`, `review`, `coordination`; keep `summarize`)
4. No warnings about missing skills appear during gateway startup or agent dispatch for cleaned agents
5. Cleaned YAMLs pass validation via `mc/yaml_validator.py`

## Tasks / Subtasks

- [x] Task 1: Fix youtube-summarizer skills (AC: #1, #4, #5)
  - [x] Edit `~/.nanobot/agents/youtube-summarizer/config.yaml`
  - [x] Replace skills list with: youtube-watcher, cron, memory, summarize
  - [x] These exist in: vendor/nanobot/nanobot/skills/ (memory, summarize, cron) and ~/.nanobot/workspace/skills/ (youtube-watcher)
- [x] Task 2: Fix image-creator-agent skills (AC: #2, #4, #5)
  - [x] Edit `~/.nanobot/agents/image-creator-agent/config.yaml`
  - [x] Replace skills list with only existing skills: skill-creator
  - [x] Remove non-existent: image-generation, design-guidelines, creative-prompting, color-theory, visual-composition, creative-direction
- [x] Task 3: Fix lead-agent skills (AC: #3, #4, #5)
  - [x] Edit `~/.nanobot/agents/lead-agent/config.yaml`
  - [x] Replace skills list with only existing skills: summarize
  - [x] Remove non-existent: orchestration, planning, task-routing, delegation, review, coordination

## Dev Notes

### Available Skills on Disk

**Vendor builtins** (`vendor/nanobot/nanobot/skills/`):
- clawhub, create-agent, cron, github, mc, memory, skill-creator, summarize, tmux, weather

**Workspace skills** (`~/.nanobot/workspace/skills/`):
- dream, extract-pdf-text, google-calendar, microsoft-calendar, youtube-watcher

### Current Invalid References

| Agent | Invalid Skills | Valid Skills to Keep |
|-------|---------------|---------------------|
| youtube-summarizer | youtube, summarization, research, content-analysis, video, transcription | youtube-watcher, cron, memory, summarize |
| image-creator-agent | image-generation, design-guidelines, creative-prompting, color-theory, visual-composition, creative-direction | skill-creator |
| lead-agent | orchestration, planning, task-routing, delegation, review, coordination | summarize |

### Key Constraint

- These files are at `~/.nanobot/agents/*/config.yaml` (home directory, not repo)
- The nanobot system agent (`~/.nanobot/agents/nanobot/config.yaml`) has `skills: [mc]` which IS valid (exists in vendor builtins)
- Remote agents have no skills section — no changes needed

### References

- [Source: vendor/nanobot/nanobot/skills/ — list of builtin skills]
- [Source: ~/.nanobot/workspace/skills/ — list of workspace skills]

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References
N/A - config-only changes, no tests required

### Completion Notes List
- Replaced youtube-summarizer skills: removed 6 invalid refs (youtube, summarization, research, content-analysis, video, transcription), added 4 valid skills (youtube-watcher, cron, memory, summarize)
- Replaced image-creator-agent skills: removed 6 invalid refs (image-generation, design-guidelines, creative-prompting, color-theory, visual-composition, creative-direction), kept 1 valid skill (skill-creator)
- Replaced lead-agent skills: removed 6 invalid refs (orchestration, planning, task-routing, delegation, review, coordination), kept 1 valid skill (summarize)
- All other YAML fields (name, role, prompt, model, display_name, soul, claude_code) left untouched

### File List
- ~/.nanobot/agents/youtube-summarizer/config.yaml (modified - skills list)
- ~/.nanobot/agents/image-creator-agent/config.yaml (modified - skills list)
- ~/.nanobot/agents/lead-agent/config.yaml (modified - skills list)
