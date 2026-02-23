# Step 5: Generate and Output

## EXECUTION RULES

- ✅ Generate the actual files now — this is the action step
- 📁 Create output directly at `~/.nanobot/agents/{agent-name}/config.yaml`
- 📁 If soul is custom, also create `~/.nanobot/agents/{agent-name}/SOUL.md`
- 🎯 The agent is registered and ready — no manual copy needed

## YOUR TASK

Generate the final agent files directly in the nanobot agents directory.

---

## GENERATE config.yaml

Create the file at `~/.nanobot/agents/{agent-name}/config.yaml`:

```yaml
name: {agent-name}
display_name: "{agent-display-name}"
role: "{agent-role}"
prompt: |
  {agent-prompt-indented-2-spaces}
model: {agent-model}
```

**Rules:**
- If `display_name` is the auto-generated form of `name`, OMIT the `display_name` line
- If `model` was not specified (user chose system default), OMIT the `model` line
- The `prompt` block MUST use `|` literal block scalar with content indented 2 spaces

---

## GENERATE SOUL.md (conditional)

### If soul-mode = custom:

Create `~/.nanobot/agents/{agent-name}/SOUL.md`:

```markdown
# Soul

I am {agent-display-name}, a nanobot agent.

## Role
{agent-role}

## Personality
{agent-personality-traits — expand into 3-5 bullet points}

## Values
{agent-values — expand into 3-5 bullet points}

## Communication Style
{agent-communication-style — 2-4 sentences}
```

### If soul-mode = auto-generated:

Skip this file. The system will auto-generate a SOUL.md when the agent first runs.

---

## SUCCESS MESSAGE

After files are created, present:

---

"Your agent `{agent-name}` is registered and ready!

**Files created:**
- `~/.nanobot/agents/{agent-name}/config.yaml`
{If custom soul: - `~/.nanobot/agents/{agent-name}/SOUL.md`}

**What happens next:**
1. Mission Control picks up the agent on next sync (or restart)
2. The agent registers with status `idle`
3. Activate it from the dashboard when ready

**Want to:**
- [A] Create another agent
- [B] Review or tweak this config
- [C] Done"

---

## HANDLING POST-GENERATE OPTIONS

**If A (create another):**
- Load: `./step-01-init.md`
- Clear previous state

**If B (review/tweak):**
- Ask what to change
- Apply changes directly to the files
- Confirm the updated file

**If C (done):**
- "All set! `{agent-name}` is ready at `~/.nanobot/agents/{agent-name}/`."
- Workflow complete

---

## SUCCESS METRICS

✅ `config.yaml` created with all required fields
✅ YAML is valid (correct indentation, list syntax)
✅ `prompt` uses literal block scalar `|`
✅ Files written directly to `~/.nanobot/agents/{agent-name}/`

## FAILURE MODES

❌ Prompt not indented correctly under `|` block scalar
❌ Model field included when user chose system default
❌ display_name included when it's just the auto-generated form
❌ Output path wrong (must be `~/.nanobot/agents/{agent-name}/config.yaml`)
