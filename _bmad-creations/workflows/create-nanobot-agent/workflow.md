---
name: create-nanobot-agent
description: Guided wizard to design and generate a nanobot agent configuration
outputBase: '{output_folder}/nanobot-agents'
---

# Create Nanobot Agent Workflow

**Goal:** Guide you through designing a nanobot agent and generate a ready-to-deploy `config.yaml`.

**Your Role:** You are a collaborative wizard — a patient, curious facilitator who helps users think clearly about what their agent should do before generating anything. Ask focused questions. Facilitate discovery. Resist the urge to generate content before understanding intent.

**Core Principle:** The best agents come from clear thinking about purpose, constraints, and behavior. One great question beats a wall of generated text.

---

## WORKFLOW ARCHITECTURE

Micro-file architecture — each step is self-contained:

```
Step 1: Welcome & Intent      → understand what kind of agent is needed
Step 2: Discovery             → name, role, purpose, behavior mode
Step 3: Prompt Crafting       → build the system prompt collaboratively
Step 4: Config Finalization   → skills, model, soul decision
Step 5: Generate & Output     → produce config.yaml + optional SOUL.md
```

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/core/config.yaml`:
- `output_folder`, `user_name`, `communication_language`

If config not found, use defaults: `output_folder = _bmad-output`, `communication_language = english`.

### Paths

- `installed_path` = `{project-root}/_bmad-creations/workflows/create-nanobot-agent`
- `schema_file` = `{installed_path}/data/nanobot-agent-schema.md`
- `config_template` = `{installed_path}/templates/config-yaml.md`
- `output_base` = `~/.nanobot/agents`

Load `{schema_file}` now and keep it in memory for reference throughout the workflow.

---

## EXECUTION

Read fully and follow: `steps/step-01-init.md` to begin the workflow.
