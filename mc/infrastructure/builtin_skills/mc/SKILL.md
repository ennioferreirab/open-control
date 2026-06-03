---
name: mc
description: "Manage Mission Control tasks. Use when user asks to create tasks, check task status, update tasks, send messages to task threads, delete or restore tasks, approve or deny work, pause or resume tasks. Keywords: task, tarefa, board, kanban, mission control, mc, tarefas, criar task, status, aprovar, negar."
---

# Mission Control Task Management

Use `exec` tool to run `nanobot mc tasks <command>` commands.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `nanobot mc tasks list` | List all tasks |
| `nanobot mc tasks list --status inbox` | Filter by status |
| `nanobot mc tasks list --json` | JSON output (for parsing) |
| `nanobot mc tasks get <id>` | Show task details + thread |
| `nanobot mc tasks get <id> --json` | Task details as JSON |
| `nanobot mc tasks create "Title"` | Create basic task |
| `nanobot mc tasks create "Title" -d "Description"` | With description |
| `nanobot mc tasks create "Title" --manual` | Human/manual task |
| `nanobot mc tasks create "Title" --trust-level human_approved` | Requires human approval |
| `nanobot mc tasks create "Title" --agent secretary` | Assign to agent |
| `nanobot mc tasks create "Title" --supervision-mode supervised` | Agent creates plan first |
| `nanobot mc tasks update-status <id> <status>` | Change status (state machine) |
| `nanobot mc tasks update-status <id> assigned --agent orchestrator-agent` | Assign to agent |
| `nanobot mc tasks send-message <id> "content"` | Post comment to thread |
| `nanobot mc tasks update-title <id> "New Title"` | Edit title |
| `nanobot mc tasks update-description <id> "New desc"` | Edit description |
| `nanobot mc tasks update-tags <id> "tag1,tag2"` | Set tags |
| `nanobot mc tasks delete <id>` | Soft-delete |
| `nanobot mc tasks restore <id>` | Restore deleted task |
| `nanobot mc tasks restore <id> --mode previous` | Restore to previous state |
| `nanobot mc tasks approve <id>` | Approve reviewed task → done |
| `nanobot mc tasks deny <id> "reason"` | Deny reviewed task (stays in review) |
| `nanobot mc tasks pause <id>` | Pause running task |
| `nanobot mc tasks resume <id>` | Resume paused task |
| `nanobot mc tasks manual-move <id> <status>` | Move manual task (bypasses state machine) |

## Task Statuses

Happy path: `inbox → assigned → in_progress → review → done`

All statuses:
- **inbox**: waiting for assignment
- **assigned**: agent assigned, not yet started
- **in_progress**: agent is working
- **review**: waiting for review/approval
- **done**: completed
- **planning**: agent is planning
- **ready**: plan ready, waiting to start
- **failed**: planning failed
- **crashed**: agent crashed
- **retrying**: being retried
- **deleted**: soft-deleted (restorable)

Valid transitions (state machine enforced):
```
inbox → assigned, planning
assigned → in_progress, assigned (reassign)
in_progress → review, done, assigned
review → done, inbox, assigned, in_progress, planning
planning → failed, review, ready, in_progress
ready → in_progress, planning, failed
failed → planning
done → assigned (reopen)
crashed → inbox, assigned
retrying → in_progress, crashed
Any state → retrying, crashed, deleted (universal)
```

## Trust Levels

| Level | Meaning | Use when |
|-------|---------|----------|
| `autonomous` | No review needed (default) | Routine tasks, low risk |
| `human_approved` | Human must approve/deny in review | Critical tasks, deployments |

## Supervision Modes

| Mode | Meaning | Use when |
|------|---------|----------|
| `autonomous` | Agent starts immediately (default) | Trust the agent's approach |
| `supervised` | Agent creates plan → user approves → executes | Want to review approach first |

## Manual Tasks

Create with `--manual`. Human-only tasks with no agent assignment.
- Use `manual-move` to change status (bypasses state machine)
- Cannot use `update-status` on manual tasks

## Common Workflows

### Create a task for an agent
```bash
exec("nanobot mc tasks create 'Summarize weekly report' -d 'Read emails and create summary' --agent secretary")
```

### Create a task that needs my approval
```bash
exec("nanobot mc tasks create 'Deploy to production' --trust-level human_approved")
```

### Create a supervised task (plan first)
```bash
exec("nanobot mc tasks create 'Refactor auth module' --supervision-mode supervised --agent orchestrator-agent")
```

### Create a personal TODO (human task)
```bash
exec("nanobot mc tasks create 'Buy groceries' --manual")
```

### Check what's happening
```bash
exec("nanobot mc tasks list")
exec("nanobot mc tasks list --status in_progress")
```

### Get task details
```bash
exec("nanobot mc tasks get <id>")
```

### Send feedback on a task
```bash
exec("nanobot mc tasks send-message <id> 'Please also include the sales numbers'")
```

### Approve completed work
```bash
exec("nanobot mc tasks approve <id>")
```

### Deny and give feedback
```bash
exec("nanobot mc tasks deny <id> 'Missing error handling for edge cases'")
```

### Pause and resume a task
```bash
exec("nanobot mc tasks pause <id>")
exec("nanobot mc tasks resume <id>")
```

### Delete and restore
```bash
exec("nanobot mc tasks delete <id>")
exec("nanobot mc tasks restore <id>")
```

### Move a manual task
```bash
exec("nanobot mc tasks manual-move <id> done")
```

## Task IDs

Task IDs are Convex document IDs (e.g., `jd7abc123xyz`). Get them from:
- `nanobot mc tasks list` (ID column)
- `nanobot mc tasks list --json` (id field)

## Important Notes

- Status changes follow the state machine. Invalid transitions will fail with an error.
- Manual tasks bypass the state machine — use `manual-move` instead of `update-status`.
- `send-message` posts a comment (no status change).
- `delete` is soft-delete. Use `restore` to bring back.
- `approve` only works on `human_approved` tasks in `review` status.
- `deny` keeps the task in `review` (does not change status).
- When using `--json` flag, output can be parsed for extracting IDs and data.
