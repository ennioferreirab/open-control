# Step 1: Welcome and Intent Discovery

## EXECUTION RULES

- 🛑 DO NOT generate a config.yaml yet — this step is discovery only
- ✅ Be welcoming and concise — don't overwhelm with info upfront
- 💬 Show presets as inspiration, not a rigid menu
- 🎯 Understand intent and working mode before moving forward
- ✅ Speak in `{communication_language}`

## YOUR TASK

Welcome the user, explain what we're building, and understand their starting point.

---

## WELCOME MESSAGE

Present this (adapt to `{communication_language}`):

---

"Hi {user_name}! Let's create a nanobot agent together.

**What's a nanobot agent?**
An autonomous AI assistant that runs in your Mission Control system. It has a role, a system prompt (its core instructions), optional skills (for task routing), and optionally a soul (personality document).

**Built-in presets you can customize or ignore:**

| Name | Role |
|------|------|
| `developer` | Software Developer — coding, debugging, code-review |
| `researcher` | Research Analyst — research, summarization, analysis |
| `writer` | Technical Writer — writing, documentation |
| `data-analyst` | Data Analyst — data-analysis, statistics |
| `devops` | DevOps Engineer — ci-cd, docker, infrastructure |
| `lead-agent` | Orchestrator — task-routing, agent-coordination |

**To get started, tell me:**
1. What should this agent do? (Or what problem are you trying to solve?)
2. Is there a preset above that's close to what you need, or is this something new?"

---

## PROCESSING USER RESPONSE

After the user responds, analyze:

**A. If they mention a preset name or something close:**
- Acknowledge it: "Great, we'll use `{preset}` as a starting point and customize from there."
- Note the preset for step-02 context
- Proceed to step-02

**B. If they describe a problem or new use case:**
- Reflect back what you understood: "So you need an agent that [restate in your words]..."
- Ask ONE clarifying question if needed to understand the core purpose
- Do NOT ask multiple questions at once
- When intent is clear, proceed to step-02

**C. If they're unsure:**
- Ask: "What task are you doing repeatedly that takes too much of your time?"
- Or: "Is there a type of work you'd like to delegate to an AI assistant?"
- Use their answer to guide them toward a purpose

## STATE TO CARRY FORWARD TO STEP-02

Before loading step-02, note internally:
- User's described intent (1-2 sentences)
- Preset reference (if any, or "custom")
- Any domain signals (e.g., "Minecraft modding", "legal research", "devops automation")

## NEXT STEP

When intent is understood, load: `./step-02-discovery.md`

Do not proceed until you have a clear understanding of what the agent is for.
