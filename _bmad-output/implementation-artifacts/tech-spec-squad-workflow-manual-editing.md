---
title: 'Squad Workflow Manual Editing And Publish-In-Place'
slug: 'squad-workflow-manual-editing'
created: '2026-03-16'
status: 'draft'
stepsCompleted: []
tech_stack: ['Next.js', 'React', 'TypeScript', 'Convex', 'vitest', 'Testing Library', 'shadcn/ui']
files_to_modify:
  - 'dashboard/features/agents/components/SquadDetailSheet.tsx'
  - 'dashboard/features/agents/components/AgentSidebar.tsx'
  - 'dashboard/features/agents/components/SquadDetailSheet.test.tsx'
  - 'dashboard/features/agents/components/AgentSidebar.test.tsx'
  - 'dashboard/convex/squadSpecs.ts'
  - 'dashboard/convex/squadSpecs.test.ts'
files_to_create:
  - 'dashboard/features/agents/components/SquadWorkflowEditor.tsx'
  - 'dashboard/features/agents/components/SquadWorkflowStepEditor.tsx'
  - 'dashboard/convex/lib/squadGraphUpdater.ts'
code_patterns:
  - 'Keep `publishGraph` for creation; add a separate in-place update mutation for published squads'
  - 'Model squad editing as a full local graph draft aligned with the Convex publish contract'
  - 'Preserve workflow document ids when editing existing workflows to avoid breaking bindings'
  - 'Treat each workflow step as an editable unit with type-specific fields'
test_patterns:
  - 'Vitest + Testing Library for squad sheet editing and agent navigation'
  - 'Convex mutation tests for validation and in-place workflow updates'
---

# Tech-Spec: Squad Workflow Manual Editing And Publish-In-Place

**Created:** 2026-03-16

## Overview

### Problem Statement

Published squads can be inspected from the UI, but they cannot be manually edited. Users cannot insert or remove workflow steps, update review behavior, add checkpoint gates, or republish the current squad spec from the squad sheet.

### Solution

Extend the squad sheet into a full editor for published squad graphs. Users edit the squad and workflows locally inside the sheet, then click `Publicar` to overwrite the current `squadSpec` and its `workflowSpecs` in Convex. The editor must support step creation, deletion, reordering, review/checkpoint configuration, and direct navigation from squad context into the selected agent view.

### Scope

**In Scope:**
- edit published squad metadata in the sheet
- edit workflow metadata and steps
- add/remove/reorder steps manually
- edit `reviewSpecId`, `onReject`, `dependsOn`, `agentKey`, `title`, and `description`
- add checkpoint steps
- show `Publicar` as the persistence action
- update the current Convex spec in place
- navigate to the corresponding agent panel when clicking an agent inside squad context

**Out of Scope:**
- versioned squad publishing
- migration of already-created mission tasks
- runtime changes for currently running workflow executions
- AI-assisted squad authoring changes

## Acceptance Signals

- the squad sheet supports inline editing of workflow steps
- clicking an agent from the squad context opens that agent view
- the publish action updates the current `squadSpec`/`workflowSpecs` in Convex
- edited squads affect future mission launches only
- targeted dashboard tests and Convex tests pass
