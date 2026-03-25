---
name: create-skill-mc
description: "Guided wizard to design and create a runtime skill for Mission Control agents. Use when the user wants to create a new skill, build a skill for agents, says 'new skill', 'create skill', 'add skill', or needs a capability packaged as a reusable skill for the MC platform."
---

# Create Skill for Mission Control

Design and create a runtime skill that MC agents can use during task execution.

This flow is terminal-first and conversational:

1. Understand what the skill should enable.
2. Discover existing skills to avoid duplication.
3. Plan the skill's structure and resources.
4. Scaffold, implement, validate, and sync.

Ask 1-2 questions at a time. Keep the flow structured but natural.

## Load Context First

Before starting, fetch the full skills catalog:

```bash
curl -s http://localhost:3000/api/specs/skills
```

Expected shape:

```json
{
  "skills": [
    {
      "name": "writing",
      "description": "Create clear written content",
      "source": "workspace",
      "always": false,
      "available": true,
      "supportedProviders": ["claude-code", "nanobot"],
      "requires": null,
      "metadata": { "categories": ["content"] }
    }
  ]
}
```

Use `?available=true` to filter to only available skills.

Use the response to:

- Check for overlap or reuse candidates before creating
- Identify skills that exist but may be unavailable (check `available` and `requires`)
- Know which providers are already supported

If a skill with similar purpose already exists, surface it immediately:

```text
A skill with similar purpose already exists:
  name: "research-synthesis"
  description: "Synthesize research findings into structured reports"
  source: workspace
  providers: claude-code, nanobot

Do you want to extend this skill instead of creating a new one?
```

## Phase 1: Intent

Understand what the skill enables and who uses it.

Collect:

- **Purpose** — what does this skill let an agent do?
- **Trigger scenarios** — when should an agent use this skill? (these become the
  `description` in frontmatter)
- **Target providers** — which providers will run this skill?
  (`claude-code`, `codex`, `nanobot`)

Start with:

- What should agents be able to do with this skill?
- Can you give an example of a task where this skill would activate?

Do not jump into structure yet.

## Phase 2: Design

Plan the skill's contents based on the intent.

### Determine the Structure Type

Guide the user through the best structure for their skill:

| Pattern | Best for | Example |
|---------|----------|---------|
| **Workflow** | Sequential processes | research → analyze → synthesize |
| **Task-based** | Tool collections | "merge PDFs", "split PDFs", "extract text" |
| **Reference** | Standards/specs | brand guidelines, coding standards |
| **Capabilities** | Integrated systems | multiple interrelated features |

### Identify Resources

For each concrete example the user provides, analyze:

1. What would an agent need to execute this from scratch?
2. What would be rewritten every time without the skill?

Map findings to resource types:

- **`scripts/`** — deterministic operations rewritten every time
  (e.g., PDF rotation, data transformation)
- **`references/`** — domain knowledge the agent lacks
  (e.g., API schemas, company policies, database docs)
- **`assets/`** — output templates or files used in results
  (e.g., boilerplate code, brand assets, document templates)

Present the design before proceeding:

```text
Skill Design Summary
─────────────────────
Name: research-synthesis
Description: Synthesize research findings into structured reports...
Structure: Workflow-based (research → analyze → synthesize)

Resources:
  references/
    - output-format.md (expected report structure)
  scripts/
    - (none needed)
  assets/
    - (none needed)

Target providers: claude-code, nanobot
```

Confirm before moving to creation.

## Phase 3: Scaffold

Create the skill directory using `init_skill.py`:

```bash
uv run python /Users/ennio/.codex/skills/.system/skill-creator/scripts/init_skill.py <skill-name> \
  --path ~/.nanobot/workspace/skills \
  --resources <comma-separated-list>
```

Only include `--resources` for directories that are actually needed.

Example:

```bash
uv run python /Users/ennio/.codex/skills/.system/skill-creator/scripts/init_skill.py research-synthesis \
  --path ~/.nanobot/workspace/skills \
  --resources references
```

## Phase 4: Implement

Write the skill contents following these principles from the Anthropic skill
standard:

### SKILL.md Frontmatter

```yaml
---
name: <skill-name>
description: <what the skill does AND when to use it — this is the trigger>
---
```

The `description` is the primary trigger. Include:
- what the skill does
- specific scenarios, file types, or tasks that activate it

Allowed frontmatter fields: `name`, `description`, `license`, `allowed-tools`,
`metadata`. No other fields.

### SKILL.md Body

**Concise is key.** The context window is shared. Only add what the agent does
not already know. Challenge each paragraph: "Does this justify its token cost?"

Rules:
- Keep under 500 lines
- Use imperative form ("Extract the data", not "This skill extracts")
- Prefer concise examples over verbose explanations
- Split into reference files when approaching the limit
- Reference files must be linked from SKILL.md with clear "when to read" notes

### Degrees of Freedom

Match specificity to fragility:

- **High freedom** — multiple valid approaches, text instructions
- **Medium freedom** — preferred pattern exists, pseudocode with parameters
- **Low freedom** — fragile/error-prone operations, specific scripts

### Progressive Disclosure

Keep SKILL.md lean. Split by domain or variant:

```text
skill-name/
├── SKILL.md            (workflow + navigation, <500 lines)
└── references/
    ├── domain-a.md     (loaded only when relevant)
    └── domain-b.md     (loaded only when relevant)
```

### Scripts

If the skill includes scripts:
- Test each script by running it
- Ensure output matches expectations
- Scripts should be executable (`chmod +x`)

### Script Path Context

Skills are mapped to `.claude/skills/<skill-name>/` in the agent's workspace.
The agent's CWD is the workspace root, NOT the skill directory.

When writing script usage examples in SKILL.md, use workspace-relative paths:

    # CORRECT — agent runs from workspace root:
    uv run python .claude/skills/<skill-name>/scripts/my_script.py --arg value

    # WRONG — assumes CWD is the skill directory:
    python scripts/my_script.py --arg value

Include a note in Quick Start:

> Scripts run from your agent workspace root. Prefix all script paths with
> `.claude/skills/<skill-name>/`.

### Codex Provider Support

If the skill targets the `codex` provider, create `agents/openai.yaml`. The
`init_skill.py` script creates this automatically. If scaffolding was skipped,
create it manually:

```yaml
name: <skill-name>
description: <same as SKILL.md description>
```

### Do NOT Create

- README.md, CHANGELOG.md, or any auxiliary documentation
- "When to Use" sections in the body (that info belongs in frontmatter description)
- Placeholder TODOs in the final version

## Phase 5: Validate and Sync

### Validate

```bash
uv run python /Users/ennio/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  ~/.nanobot/workspace/skills/<skill-name>
```

Fix any errors before proceeding.

### Register the Skill

Register via API (writes SKILL.md to disk and syncs to Convex):

```bash
curl -s -X POST http://localhost:3000/api/specs/skills \
  -H "Content-Type: application/json" \
  -d '{
    "name": "<skill-name>",
    "description": "<what it does and when to use it>",
    "content": "<full SKILL.md body content>",
    "source": "workspace",
    "supportedProviders": ["claude-code"],
    "available": true
  }'
```

MCP agents can also use the `register_skill` tool directly.

### Verify

Re-fetch context to confirm the skill appears:

```bash
curl -s http://localhost:3000/api/specs/skills | python3 -c "
import json, sys
ctx = json.load(sys.stdin)
skills = [s for s in ctx.get('skills', []) if s['name'] == '<skill-name>']
print(json.dumps(skills, indent=2) if skills else 'NOT FOUND')
"
```

## Phase 6: Review

Present a final summary before declaring done:

```text
═══════════════════════════════════════
  Skill Created Successfully
═══════════════════════════════════════
Name:        <skill-name>
Description: <description>
Location:    ~/.nanobot/workspace/skills/<skill-name>/
Structure:   <pattern used>

Files:
  SKILL.md                 (<line count> lines)
  references/domain.md     (if created)
  scripts/transform.py     (if created)
  agents/openai.yaml       (if created)

Providers:   claude-code, nanobot
Synced:      yes
Validated:   yes
═══════════════════════════════════════
```

Offer next steps:

- Test the skill by assigning it to an agent
- Create another skill
- Create a squad that uses this skill (`/create-squad-mc`)

## Contract Rules

- Never create a skill that duplicates an existing `availableSkills` entry without
  explicit confirmation
- Every skill must pass `quick_validate.py` before sync
- Every skill must be synced to Convex after creation
- The `description` frontmatter field must include trigger scenarios, not just
  what the skill does
- Do not add frontmatter fields beyond: `name`, `description`, `license`,
  `allowed-tools`, `metadata`
- Skills target `~/.nanobot/workspace/skills/` (runtime), NOT `~/.claude/skills/`
  (authoring) or `mc/skills/` (builtin — requires commit)
