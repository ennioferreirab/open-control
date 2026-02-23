# Step 3: System Prompt Crafting

## EXECUTION RULES

- ✅ Generate a DRAFT prompt based on step-02 discovery — then refine collaboratively
- 💬 Present the draft and ask what feels right or wrong
- 🎯 The prompt is the most important field — invest here
- 🚫 Do NOT rush to a final version — one round of refinement minimum
- ✅ Use step-02 context: name, role, behavior-mode, responsibilities, constraints

## WHAT MAKES A GREAT NANOBOT PROMPT

A good system prompt for a nanobot agent:
1. **States identity clearly** — who the agent is and what it specializes in
2. **Defines the operating mode** — how it approaches tasks (methodically, creatively, etc.)
3. **Lists core capabilities** — what it's good at and expected to do
4. **States explicit constraints** — what it doesn't do or escalates
5. **Defines output style** — how it communicates results
6. **Sets collaboration norms** — how it works with other agents (if orchestrator/hybrid)

Length guide: 150-400 words. Long enough to be specific, short enough to stay focused.

---

## DRAFT GENERATION

Generate a draft prompt using this structure:

```
You are [display_name], [role].

[2-3 sentences establishing identity, specialization, and approach]

**Core responsibilities:**
- [responsibility 1]
- [responsibility 2]
- [responsibility 3]

**How you work:**
[1-2 sentences about working style, methodology, output quality standards]

**Scope:**
[What you handle vs. what you escalate or decline]

[If orchestrator/hybrid: sentence about how you coordinate with other agents]
```

Fill this template using the step-02 discoveries. Be specific — avoid vague words like "helpful", "efficient", "best practices" unless tied to concrete behavior.

---

## PRESENTING THE DRAFT

Present the draft prompt in a code block, then ask:

---

"Here's a draft system prompt for `{agent-name}`:

```
[DRAFT PROMPT HERE]
```

**A few questions to sharpen this:**
1. Does the identity section (first paragraph) feel right? Too formal? Too casual?
2. Are the core responsibilities accurate and complete?
3. Is there anything the agent should *always* do that's missing?

What would you change?"

---

## REFINEMENT LOOP

After user feedback:

1. Apply requested changes
2. If changes are significant, show the updated version
3. Ask: "Better? Or more to adjust?"
4. Repeat until user is satisfied (max 3 rounds before asking "want me to finalize this?")

**If user says "looks good" or confirms:** Lock the prompt and proceed.

**If user is unsure about something specific:** Ask a targeted question.
Example: "You mentioned it should handle code reviews — should it also suggest architectural improvements, or stay focused on code-level feedback?"

---

## SOUL DECISION

After the prompt is confirmed, ask:

---

"Should this agent have a **soul** — a personality document that makes it more distinct and human-like in interactions?

- **Yes**: I'll help you define personality traits, values, and communication style
- **No / Skip**: The agent will use an auto-generated soul template

A soul is most useful for agents the user interacts with conversationally. Less important for purely automated/background agents."

---

### If user says Yes to soul:

Ask:
> "Describe the agent's personality in a few words. (e.g., 'direct and no-nonsense', 'warm but precise', 'skeptical but constructive')"

Then ask:
> "What values guide it? What does it care about getting right?"

Note these for step-04.

### If user says No / Skip:

Note `soul = auto-generated`.

---

## STATE TO CARRY FORWARD TO STEP-04

- `agent-prompt` (confirmed final text)
- `soul-mode` (custom | auto-generated)
- `soul-personality` (if custom: personality traits, values, communication style)

## NEXT STEP

When prompt is confirmed and soul decision made, load: `./step-04-config.md`
