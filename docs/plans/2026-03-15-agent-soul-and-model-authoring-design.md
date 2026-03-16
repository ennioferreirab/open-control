# Agent Soul And Model Authoring Design

**Date:** 2026-03-15

**Objective:** Make squad-created agents carry the full canonical authoring contract, surface `Soul` in agent detail with editing support, fix the disabled `Save` bug in the agent panel, and expose model selection clearly in squad authoring.

## Goal

Keep `Create Agent`, `Create Squad`, and the agent detail panel aligned around one canonical agent contract. New squad-created agents must carry `prompt`, `model`, `skills`, and `soul`. The squad authoring flow must show available models and report the chosen model per agent. The agent panel must show and allow editing of `Soul`, and saving must reliably enable when the operator changes `Prompt`, `Model`, or `Soul`.

## Approved Scope

- Confirm and preserve `prompt`, `model`, `skills`, and `soul` on agents created through `/create-squad-mc`.
- Extend squad-authoring context to include available models.
- Update `/create-squad-mc` instructions so new squad agents explicitly choose `model`, `skills`, and `soul`.
- Include chosen models and a short `soul` preview in the final squad summary.
- Add `Soul` preview and editing to the agent detail panel.
- Fix the `AgentConfigSheet` dirty-state/save logic so `Save` enables when `Prompt`, `Model`, or `Soul` changes.

## Problems in the Current Model

- The panel opened from `AgentSidebar` does not render `Soul`, so operators cannot inspect or edit it there.
- The squad authoring context exposes reusable agents and skills but not the list of connected models, so model choice is underspecified in `Create Squad`.
- `/create-squad-mc` instructs collection of canonical fields, but the available model list and final report do not make model selection explicit enough.
- The final squad summary does not show chosen models, and it does not show a readable `Soul` preview.
- `AgentConfigSheet` computes dirty state from a model-mode abstraction that can fail to recognize certain real model edits, causing `Save` to stay disabled even after user changes.

## Core Decisions

### 1. Canonical squad agent specs stay explicit

The authoring contract for squad agents remains explicit. Each squad-authored agent entry should carry:

- `name`
- `displayName`
- `role`
- `prompt`
- `model`
- `skills`
- `soul`

The system should not silently infer these fields at publish time when the authoring flow can collect them directly.

### 2. Squad authoring gets a first-class model catalog

The squad-authoring context route should return `availableModels` alongside `activeAgents` and `availableSkills`. This keeps `Create Squad` aligned with the same model source already used by the agent panel and settings.

### 3. Agent detail owns `Soul` visibility and editing

`AgentConfigSheet` should add a `Soul` section next to the existing authoring metadata. It should show a short preview inline, allow full editing through the same modal pattern already used for prompt/memory/history, and persist edits to both Convex and YAML.

### 4. Dirty state should compare the persisted form contract, not only UI mode

The `Save` enablement logic should reflect the actual persisted fields. If the operator changes `Prompt`, `Model`, `Soul`, `Skills`, or other persisted fields, `isDirty` should become `true` regardless of whether the stored model string came from `default`, `tier`, `custom`, or `cc` mode.

## UX Behavior

### Agent Detail Panel

- Add a `Soul` section below `Prompt`.
- Show a short inline preview for `Soul`.
- Add an `Edit` affordance matching the panel's existing text-edit pattern.
- Persist `Soul` alongside other editable agent fields.

### Squad Authoring

- Context includes `availableModels`.
- The flow lists those models when the user defines a new squad agent.
- The assistant asks for a model selection for every new agent.
- The final report shows, per agent:
  - `model`
  - `skills`
  - a short `soul` preview

## Data and Flow Changes

### Squad Authoring Context

- Extend `GET /api/specs/squad/context` to include `availableModels` sourced from the `connected_models` setting.
- Keep `activeAgents` and `availableSkills` unchanged.

### Agent Panel Persistence

- Extend the panel save path so `Soul` is included in:
  - the Convex `agents.updateConfig` mutation
  - the YAML write endpoint at `/api/agents/[agentName]/config`

### `/create-squad-mc` Skill Contract

- Update the skill guidance so agent specs explicitly include `model`, `skills`, and `soul`.
- Update the final summary template to print the chosen model and a concise soul preview.

## Risks and Tradeoffs

### Risk: `Soul` previews become noisy

Showing full `Soul` text inline would overwhelm the panel and final report. The UI and squad summary should show only a short preview, with full content available in edit/view mode.

### Risk: save logic remains tied to UI state

If dirty-state logic stays coupled to presentation-specific model modes, the save bug will recur. The safer design is to compare persisted field values directly.

## Recommended Delivery Shape

1. Add tests that fail for the missing `Soul` section, missing squad context models, and disabled save-state regression.
2. Implement `Soul` rendering and editing in `AgentConfigSheet`.
3. Fix panel dirty-state detection and save persistence for `Soul` and model edits.
4. Extend the squad-authoring context route to include available models.
5. Update `/create-squad-mc` locally so model choice, skills, and soul are explicit and reported in the final summary.
