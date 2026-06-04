---
name: mc
description: "Manage Mission Control tasks. Use when user asks to create tasks, check task status, update tasks, send messages to task threads, delete or restore tasks, approve or deny work, pause or resume tasks. Keywords: task, tarefa, board, kanban, mission control, mc, tarefas, criar task, status, aprovar, negar."
---

# Mission Control Task Management

Use `exec` tool to run `open-control mc tasks <command>` commands.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `open-control mc tasks list` | List all tasks |
| `open-control mc tasks list --status inbox` | Filter by status |
| `open-control mc tasks list --json` | JSON output (for parsing) |
| `open-control mc tasks get <id>` | Show task details + thread |
| `open-control mc tasks get <id> --json` | Task details as JSON |
| `open-control mc tasks create "Title"` | Create basic task |
| `open-control mc tasks create "Title" -d "Description"` | With description |
| `open-control mc tasks create "Title" --manual` | Human/manual task |
| `open-control mc tasks create "Title" --trust-level human_approved` | Requires human approval |
| `open-control mc tasks create "Title" --agent secretary` | Assign to agent |
| `open-control mc tasks create "Title" --supervision-mode supervised` | Agent creates plan first |
| `open-control mc tasks update-status <id> <status>` | Change status (state machine) |
| `open-control mc tasks update-status <id> assigned --agent orchestrator-agent` | Assign to agent |
| `open-control mc tasks send-message <id> "content"` | Post comment to thread |
| `open-control mc tasks update-title <id> "New Title"` | Edit title |
| `open-control mc tasks update-description <id> "New desc"` | Edit description |
| `open-control mc tasks update-tags <id> "tag1,tag2"` | Set tags |
| `open-control mc tasks delete <id>` | Soft-delete |
| `open-control mc tasks restore <id>` | Restore deleted task |
| `open-control mc tasks restore <id> --mode previous` | Restore to previous state |
| `open-control mc tasks approve <id>` | Approve reviewed task → done |
| `open-control mc tasks deny <id> "reason"` | Deny reviewed task (stays in review) |
| `open-control mc tasks pause <id>` | Pause running task |
| `open-control mc tasks resume <id>` | Resume paused task |
| `open-control mc tasks manual-move <id> <status>` | Move manual task (bypasses state machine) |

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
exec("open-control mc tasks create 'Summarize weekly report' -d 'Read emails and create summary' --agent secretary")
```

### Create a task that needs my approval
```bash
exec("open-control mc tasks create 'Deploy to production' --trust-level human_approved")
```

### Create a supervised task (plan first)
```bash
exec("open-control mc tasks create 'Refactor auth module' --supervision-mode supervised --agent orchestrator-agent")
```

### Create a personal TODO (human task)
```bash
exec("open-control mc tasks create 'Buy groceries' --manual")
```

### Check what's happening
```bash
exec("open-control mc tasks list")
exec("open-control mc tasks list --status in_progress")
```

### Get task details
```bash
exec("open-control mc tasks get <id>")
```

### Send feedback on a task
```bash
exec("open-control mc tasks send-message <id> 'Please also include the sales numbers'")
```

### Approve completed work
```bash
exec("open-control mc tasks approve <id>")
```

### Deny and give feedback
```bash
exec("open-control mc tasks deny <id> 'Missing error handling for edge cases'")
```

### Pause and resume a task
```bash
exec("open-control mc tasks pause <id>")
exec("open-control mc tasks resume <id>")
```

### Delete and restore
```bash
exec("open-control mc tasks delete <id>")
exec("open-control mc tasks restore <id>")
```

### Move a manual task
```bash
exec("open-control mc tasks manual-move <id> done")
```

## Task IDs

Task IDs are Convex document IDs (e.g., `jd7abc123xyz`). Get them from:
- `open-control mc tasks list` (ID column)
- `open-control mc tasks list --json` (id field)

## Important Notes

- Status changes follow the state machine. Invalid transitions will fail with an error.
- Manual tasks bypass the state machine — use `manual-move` instead of `update-status`.
- `send-message` posts a comment (no status change).
- `delete` is soft-delete. Use `restore` to bring back.
- `approve` only works on `human_approved` tasks in `review` status.
- `deny` keeps the task in `review` (does not change status).
- When using `--json` flag, output can be parsed for extracting IDs and data.
