# Step 2: Agent Discovery

## EXECUTION RULES

- 🛑 DO NOT generate the prompt yet — that's step-03
- ✅ Collect the four core decisions: name, role, behavior mode, scope
- 💬 Ask 1-2 questions at a time maximum — this is a conversation
- 🔍 Probe for what the agent should NOT do (constraints matter)
- ✅ If preset was selected, pre-fill sensible defaults and confirm

## YOUR TASK

Gather the specific information needed to define the agent's identity and behavior boundaries.

---

## DISCOVERY CONVERSATION

Work through these topics in a natural conversation. You don't need to ask them in order — read the context and adapt.

### Topic A: Agent Name and Display Name

Ask:
> "What would you like to call this agent? I need a slug (e.g., `code-reviewer`, `legal-analyst`) and optionally a display name (e.g., 'Code Reviewer')."

Rules to validate mentally:
- Slug: lowercase, alphanumeric + hyphens only
- If they give "My Agent" or "Code Reviewer", suggest the slug: `my-agent`, `code-reviewer`
- Display name: auto-generated if not specified (e.g., `code-reviewer` → "Code Reviewer")

### Topic B: Role

Ask:
> "In one sentence, what is this agent's professional role? (e.g., 'Senior Backend Developer specializing in Python APIs')"

Guide them toward specificity. "Developer" is too vague. "Python backend developer focused on API design and code review" is better.

### Topic C: Behavior Mode — Executor vs Orchestrator

Ask:
> "Does this agent *do work itself* (write code, draft documents, analyze data), or does it *coordinate other agents* and delegate tasks?"

- **Executor**: takes a task, produces output
- **Orchestrator**: breaks tasks into subtasks, assigns to other agents, tracks progress
- **Hybrid**: mostly executes but can coordinate when needed

This shapes the prompt significantly. Note the answer.

### Topic D: Scope and Constraints

Ask ONE of these depending on context:
> "What are the 2-3 most important things this agent should always do?"
> "What should this agent absolutely NOT do? What's out of scope?"

Both questions are valuable. Ask at least one. The constraints are often more important than the capabilities.

### Topic E: Context and Tools (if relevant)

If the agent works with specific tools or systems, ask:
> "Does this agent need to work with any specific systems, files, or APIs? (e.g., Git repos, databases, external services)"

---

## SUMMARY AND CONFIRMATION

Once you've collected name, role, behavior mode, and scope, present a summary:

---

"Here's what I have so far:

**Name:** `{agent-name}` (display: "{agent-display-name}")
**Role:** {agent-role}
**Mode:** {executor|orchestrator|hybrid}
**Core responsibilities:** {1-3 bullet points}
**Constraints/out of scope:** {constraints if any}

Does this capture what you want, or should we adjust anything?"

---

## PROCESSING CONFIRMATION

**If user confirms:** Note all values internally and proceed to step-03.

**If user wants to adjust:** Make the adjustments, re-present the summary, and confirm again.

**If user adds new info:** Incorporate it, update the summary, confirm.

## STATE TO CARRY FORWARD TO STEP-03

- `agent-name` (slug)
- `agent-display-name` (title case)
- `agent-role` (one sentence)
- `behavior-mode` (executor/orchestrator/hybrid)
- `core-responsibilities` (2-4 items)
- `constraints` (what it should NOT do)
- `domain-context` (tools, systems, domain specifics)

## NEXT STEP

When summary is confirmed, load: `./step-03-prompt.md`
