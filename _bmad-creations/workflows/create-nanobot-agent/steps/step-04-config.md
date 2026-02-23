# Step 4: Config Finalization

## EXECUTION RULES

- ✅ This step is fast — collecting the last config fields
- 💬 Present sensible defaults based on role and behavior-mode
- ✅ Ask about model only if the user seems to have a preference — default is fine for most
- ℹ️ Skills are NOT discussed in this step — they can be added manually later

## YOUR TASK

Finalize model selection and do a complete config review before generating.
Skills are omitted from the config (can be added manually after install).

---

## MODEL SELECTION

Ask:

---

"**Model choice** (optional — system default is used if not specified):

| Model | Best For |
|-------|----------|
| `claude-haiku-4-5` | Fast, simple, high-volume tasks |
| `claude-sonnet-4-6` | Most tasks — good balance (recommended) |
| `claude-opus-4-6` | Complex reasoning, orchestration, important decisions |

What's this agent's primary workload? I'll suggest the right model, or you can specify one directly."

---

### Model Recommendation Logic

Use the agent's behavior-mode and responsibilities to recommend:

- **Orchestrator / complex reasoning**: `claude-opus-4-6`
- **Most executors (coding, writing, research, analysis)**: `claude-sonnet-4-6`
- **Simple, high-frequency tasks (triage, summaries, routing)**: `claude-haiku-4-5`
- **User says "I want to decide later" or "system default"**: Omit the model field entirely

---

## COMPLETE CONFIG REVIEW

Once model is confirmed, present the full config for review:

---

"Here's the complete configuration for `{agent-name}`:

```yaml
name: {agent-name}
display_name: "{agent-display-name}"
role: "{agent-role}"
prompt: |
  {agent-prompt}
model: {agent-model}
```

{If soul is custom:}
**SOUL.md** will also be generated with the personality you described.

**Everything look correct?**
- [Y] Yes, generate the files
- [N] I want to change something"

---

## HANDLING FINAL CHANGES

If user wants a change:
- Ask what specifically
- Apply it
- Show only the changed section, then ask: "Updated — ready to generate?"

If user confirms (Y or similar): proceed to step-05.

---

## STATE TO CARRY FORWARD TO STEP-05

Complete config object:
- `agent-name`
- `agent-display-name`
- `agent-role`
- `agent-prompt`
- `agent-model` (or null if omitted)
- `soul-mode` (custom | auto-generated)
- `soul-content` (if custom: personality, values, communication style)

## NEXT STEP

When user confirms the config, load: `./step-05-generate.md`
