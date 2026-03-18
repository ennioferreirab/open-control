---
title: 'Squad Workflow Canvas And Agent Overlay Sheet'
slug: 'squad-workflow-canvas-overlay'
created: '2026-03-16'
status: 'draft'
stepsCompleted: []
tech_stack: ['Next.js', 'React', 'TypeScript', 'Convex', '@xyflow/react', 'dagre', 'vitest']
files_to_modify:
  - 'dashboard/features/agents/components/SquadDetailSheet.tsx'
  - 'dashboard/features/agents/components/SquadDetailSheet.test.tsx'
  - 'dashboard/features/agents/hooks/useUpdatePublishedSquad.ts'
files_to_create:
  - 'dashboard/features/agents/components/SquadWorkflowCanvas.tsx'
  - 'dashboard/features/agents/components/SquadWorkflowCanvas.test.tsx'
code_patterns:
  - 'Reuse Execution Plan canvas patterns without coupling squad editing to task runtime logic'
  - 'Open AgentConfigSheet as an overlay sheet above the squad sheet'
  - 'Keep squad workflow edits in local draft state until Publicar'
test_patterns:
  - 'Canvas interaction tests for node selection and step edits'
  - 'Overlay-sheet regression tests preserving squad context'
---

# Tech-Spec: Squad Workflow Canvas And Agent Overlay Sheet

**Created:** 2026-03-16

## Overview

### Problem Statement

The current squad editor works, but the workflow is still more list-oriented than the execution-plan canvas, and opening an agent from squad context replaces the squad content instead of layering the agent UI above it.

### Solution

Render the squad workflow inside a canvas that matches the execution-plan editing experience and open the standard agent sheet as an over-sheet above the squad. Agents in the squad should also be shown in a cleaner grid layout.

### Scope

**In Scope:**
- workflow canvas styled and interacted with like `Execution Plan`
- node-based editing of squad workflow steps
- agent card grid in squad view
- overlay agent sheet above the squad
- publish flow still updating the current Convex spec

**Out of Scope:**
- persisting custom node positions
- changing task execution runtime semantics
- replacing the existing registered-agent sheet implementation

## Acceptance Signals

- squad workflow renders and edits through a canvas
- agent cards open an over-sheet while squad stays visible underneath
- publish still writes the current workflow graph to Convex
- targeted dashboard tests and guardrails pass
