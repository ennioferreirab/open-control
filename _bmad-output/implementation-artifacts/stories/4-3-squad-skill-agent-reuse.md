# Story: Update Create Squad Skill — Agent Reuse Emphasis

## Story
As a user creating a squad, I want the skill to strongly prefer reusing my existing agents instead of creating new ones, so I don't end up with a proliferation of similar agents that cause confusion.

## Status: done

## Context
The current `/create-squad-mc` skill's Phase 4 mentions reuse but doesn't enforce it strongly enough. Users end up with many similar agents. We need to add a mandatory Reuse Assessment step and a hard rule that halts if 3+ new agents would be created.

## Acceptance Criteria
- [x] Phase 4 begins with a mandatory "Reuse Assessment" before any agent design
- [x] Each required capability is explicitly evaluated against `activeAgents`
- [x] Reuse is the default recommendation — creation is the exception
- [x] Hard rule: if 3+ new agents would be created, the skill halts and asks for explicit confirmation
- [x] The assessment output format shows match percentage, reasoning, and recommendation (REUSE / CREATE NEW)
- [x] Existing Phase 4 functionality (naming, contract fields, roster presentation) is preserved

## Tasks

- [x] **Modify `mc/skills/create-squad-mc/SKILL.md` — Phase 4 Agent Design**

  Add new "Agent Reuse Priority (Mandatory)" section at the TOP of Phase 4, before the existing content:

  ```markdown
  ### Agent Reuse Priority (Mandatory)

  ALWAYS prefer reusing existing agents over creating new ones. Too many agents
  cause confusion and fragmentation. Only create a new agent when NO existing
  agent is a credible match for the required capability.

  Before proposing any roster, you MUST produce a Reuse Assessment for every
  required capability identified in Phase 2:

  ​```text
  Reuse Assessment:
    Capability "audience research":
      Match: researcher-agent (85% fit) — has research-synthesis skill, used in content squads
      Recommendation: REUSE

    Capability "long-form drafting":
      Match: post-writer (90% fit) — has writing skill, same model target
      Recommendation: REUSE

    Capability "editorial review":
      Match: none — no existing agent with editorial-review skill
      Recommendation: CREATE NEW
  ​```

  Rules:
  - A match of 60%+ fit means REUSE. Present the candidate and confirm with the user.
  - A partial match (40-59%) means ASK — show the candidate and let the user decide.
  - Below 40% or no match means CREATE NEW is acceptable.
  - **Hard rule:** if you would create 3 or more new agents, STOP. List all
    proposed new agents, explain why existing agents cannot be reused for each,
    and get explicit user confirmation before proceeding.
  ```

  Update the existing "Reuse Rules" subsection to reinforce this:
  - Change opening from "When a plausible reuse candidate exists:" to "Reuse is the default. For every capability, the Reuse Assessment above determines the action:"
  - Keep the existing 3-step reuse flow (show candidate, ask, preserve contract)

## File List
- `mc/skills/create-squad-mc/SKILL.md` (modify — Phase 4 only)

## Dev Notes
- **Do NOT change Phases 1-3 or 5-6.** Only modify Phase 4.
- **Preserve existing contract rules** at the bottom of the file. The naming standard, roster presentation format, and required fields (`displayName`, `prompt`, `model`, `skills`, `soul`) remain unchanged.
- **The `activeAgents` data** is already fetched in the "Load Context First" section from `/api/specs/squad/context`. The Reuse Assessment uses this data.
- **Fit percentage** is a heuristic the LLM estimates based on skill overlap, role similarity, and model compatibility. It doesn't need to be computed — it's a judgment call presented to the user.

## Testing Standards
- Manual testing: run `/create-squad-mc` and verify the Reuse Assessment appears before any agent is proposed
- Verify the hard rule triggers when attempting to create 3+ agents

## Dev Agent Record
- Model: claude-sonnet-4-6
- Completion notes: Added "Agent Reuse Priority (Mandatory)" section at the top of Phase 4 with the Reuse Assessment format, fit percentage heuristics (60%+ REUSE, 40-59% ASK, below 40% CREATE NEW), and the hard rule halting at 3+ new agents. Updated "Reuse Rules" opening to reuse-first language. Phases 1-3, 5-6, and Contract Rules are unchanged.
- Files modified: mc/skills/create-squad-mc/SKILL.md
