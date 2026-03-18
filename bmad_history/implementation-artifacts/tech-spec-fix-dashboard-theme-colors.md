---
title: 'Fix Dashboard Theme Colors'
slug: 'fix-dashboard-theme-colors'
created: '2026-02-23'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Next.js 15', 'Tailwind CSS 3.4', 'shadcn/ui', 'next-themes 0.4', 'CSS Variables (HSL)', 'Radix UI']
files_to_modify: ['components/DashboardLayout.tsx', 'components/AgentSidebar.tsx', 'components/AgentSidebarItem.tsx', 'components/ActivityFeedPanel.tsx', 'components/ActivityFeed.tsx', 'components/FeedItem.tsx', 'components/KanbanColumn.tsx', 'components/KanbanBoard.tsx', 'components/TaskCard.tsx', 'components/TaskInput.tsx', 'components/TaskDetailSheet.tsx', 'components/ExecutionPlanTab.tsx', 'components/ThreadMessage.tsx', 'lib/constants.ts']
code_patterns: ['CSS variable tokens (bg-background, text-foreground, bg-card, etc.)', 'HSL-based theme variables in globals.css :root and .dark', 'next-themes ThemeProvider with attribute="class"', 'darkMode: ["selector", "class"] in tailwind config', 'cn() utility for class merging (clsx + tailwind-merge)']
test_patterns: ['Vitest + React Testing Library', 'Test files colocated as *.test.tsx', 'Some tests assert on hardcoded class names (need updating)']
---

# Tech-Spec: Fix Dashboard Theme Colors

**Created:** 2026-02-23

## Overview

### Problem Statement

The dashboard has broken theme colors. Custom components use hardcoded Tailwind color classes (`bg-white`, `text-slate-900`, `border-slate-200`) instead of CSS variable-based theme tokens. This causes visual mismatch — elements render with fixed light-mode colors regardless of theme selection, while shadcn/ui components correctly respond to dark/light mode. Additionally, the "Assigned" and "In Progress" status colors in `lib/constants.ts` are nearly identical (both blue variants), making them hard to distinguish.

### Solution

Replace all hardcoded color classes with theme-aware CSS variable tokens (`bg-background`, `text-foreground`, `bg-card`, etc.) across all 13 custom components. Differentiate Assigned vs In Progress status colors and add dark mode variants to the status color system.

### Scope

**In Scope:**
- Replace hardcoded Tailwind color classes with CSS variable tokens across all 13 affected components
- Differentiate Assigned vs In Progress status colors in `lib/constants.ts`
- Add dark mode variants for status colors
- Update test files that assert on hardcoded class names
- Ensure full light/dark mode support via the existing ThemeToggle

**Out of Scope:**
- Layout or structural changes
- Redesigning the overall color palette or brand colors
- Changes to shadcn/ui base components (already use tokens correctly)

## Context for Development

### Codebase Patterns

- Theme colors defined as HSL CSS variables in `app/globals.css` under `:root` (light) and `.dark` selectors
- shadcn/ui components correctly reference theme tokens: `bg-background`, `text-foreground`, `bg-card`, etc.
- `next-themes` ThemeProvider configured with `attribute="class"` in `app/layout.tsx`
- Tailwind config: `darkMode: ["selector", "class"]`
- `cn()` utility from `lib/utils.ts` merges classes safely via clsx + tailwind-merge
- Sidebar component from shadcn/ui (`components/ui/sidebar.tsx`) is the gold standard reference for correct token usage

### Color Token Mapping (hardcoded -> theme-aware)

| Hardcoded Class | Theme Token Replacement | Usage Context |
|---|---|---|
| `bg-white` | `bg-background` | Page/section backgrounds |
| `text-slate-900` | `text-foreground` | Primary text, headings |
| `text-slate-800` | `text-foreground` | Strong body text |
| `text-slate-700` | `text-foreground` | Body text |
| `text-slate-600` | `text-muted-foreground` | Secondary body text |
| `text-slate-500` | `text-muted-foreground` | Muted/helper text |
| `text-slate-400` | `text-muted-foreground` | Placeholder/disabled text |
| `text-slate-300` | `text-muted-foreground` | Very muted icons |
| `bg-slate-50` | `bg-muted` | Subtle backgrounds |
| `bg-slate-100` | `bg-muted` | Highlighted/hover backgrounds |
| `border-slate-200` | `border-border` | All borders |
| `hover:bg-slate-100` | `hover:bg-accent` | Interactive hover states |
| `hover:text-slate-700` | `hover:text-accent-foreground` | Interactive hover text |

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `app/globals.css` | CSS variable definitions for light/dark themes |
| `tailwind.config.ts` | Tailwind theme extension with CSS variable mappings |
| `components/ui/sidebar.tsx` | Gold standard reference for correct theme token usage |
| `components/ThemeToggle.tsx` | Existing light/dark/system toggle |
| `lib/utils.ts` | `cn()` utility for class merging |

### Technical Decisions

- Use existing CSS variable tokens from shadcn/ui — no new CSS variables needed
- Light mode is the primary/default theme
- Status colors: change "assigned" from blue to cyan/teal to differentiate from "in_progress" (blue)
- Status colors get `dark:` prefix variants for dark mode support
- Test files that assert on hardcoded class names need updating to match new tokens

## Implementation Plan

### Tasks

- [ ] Task 1: Update STATUS_COLORS in `lib/constants.ts`
  - File: `lib/constants.ts`
  - Action: Change "assigned" from blue to cyan (`border-l-cyan-500`, `bg-cyan-100 dark:bg-cyan-950`, `text-cyan-700 dark:text-cyan-300`). Add `dark:` variants to ALL status colors for dark mode. Keep "in_progress" as blue.
  - New STATUS_COLORS values:
    ```
    inbox:       border-l-violet-500, bg-violet-100 dark:bg-violet-950, text-violet-700 dark:text-violet-300
    assigned:    border-l-cyan-500, bg-cyan-100 dark:bg-cyan-950, text-cyan-700 dark:text-cyan-300
    in_progress: border-l-blue-500, bg-blue-100 dark:bg-blue-950, text-blue-700 dark:text-blue-300
    review:      border-l-amber-500, bg-amber-100 dark:bg-amber-950, text-amber-700 dark:text-amber-300
    done:        border-l-green-500, bg-green-100 dark:bg-green-950, text-green-700 dark:text-green-300
    retrying:    border-l-amber-600, bg-amber-100 dark:bg-amber-950, text-amber-700 dark:text-amber-300
    crashed:     border-l-red-500, bg-red-100 dark:bg-red-950, text-red-700 dark:text-red-300
    ```
  - Notes: This is the foundation — other components consume these values. Do this first.

- [ ] Task 2: Fix `components/DashboardLayout.tsx`
  - File: `components/DashboardLayout.tsx`
  - Action: Replace all hardcoded color classes:
    - Line 54: `bg-white` -> `bg-background`
    - Line 55: `text-slate-500` -> `text-muted-foreground`
    - Line 66: `bg-white` -> `bg-background`
    - Line 67: `border-slate-200` -> `border-border`
    - Line 68: `text-slate-900` -> `text-foreground`
    - Line 74: `text-slate-500 hover:bg-slate-100 hover:text-slate-700` -> `text-muted-foreground hover:bg-accent hover:text-accent-foreground`
    - Line 80: `border-slate-200` -> `border-border`

- [ ] Task 3: Fix `components/AgentSidebar.tsx`
  - File: `components/AgentSidebar.tsx`
  - Action: Replace all hardcoded color classes:
    - Line 23: `border-slate-200` -> `border-sidebar-border`
    - Line 25: `text-slate-500` -> `text-sidebar-foreground/70`
    - Line 26: `text-slate-900` -> `text-sidebar-foreground`
    - Line 35: `text-slate-500` -> `text-muted-foreground`
    - Line 37: `bg-slate-100` -> `bg-muted`
    - Line 50: `border-slate-200` -> `border-sidebar-border`
  - Notes: Use `sidebar-*` tokens here since this is inside the Sidebar component, matching shadcn patterns.

- [ ] Task 4: Fix `components/AgentSidebarItem.tsx`
  - File: `components/AgentSidebarItem.tsx`
  - Action: Replace hardcoded color classes:
    - Line 13: `bg-slate-400` -> `bg-muted-foreground`
    - Line 89: `text-slate-900` -> `text-sidebar-foreground`
    - Line 92: `text-slate-500` -> `text-sidebar-foreground/70`

- [ ] Task 5: Fix `components/ActivityFeedPanel.tsx`
  - File: `components/ActivityFeedPanel.tsx`
  - Action: Replace hardcoded color classes:
    - Line 13: `border-slate-200 bg-slate-50` -> `border-border bg-muted`
    - Line 29: `border-slate-200 bg-slate-50` -> `border-border bg-muted`
    - Line 30: `border-slate-200` -> `border-border`
    - Line 31: `text-slate-900` -> `text-foreground`

- [ ] Task 6: Fix `components/ActivityFeed.tsx`
  - File: `components/ActivityFeed.tsx`
  - Action: Replace hardcoded color classes:
    - Line 87: `text-slate-400` -> `text-muted-foreground`
    - Line 98: `text-slate-400` -> `text-muted-foreground`

- [ ] Task 7: Fix `components/FeedItem.tsx`
  - File: `components/FeedItem.tsx`
  - Action: Replace hardcoded color classes:
    - Line 31: `text-slate-400` -> `text-muted-foreground`
    - Line 35: `text-slate-700` -> `text-foreground`
    - Line 40: `text-slate-500` -> `text-muted-foreground`

- [ ] Task 8: Fix `components/KanbanColumn.tsx`
  - File: `components/KanbanColumn.tsx`
  - Action: Replace hardcoded color classes:
    - Line 44: `text-slate-900` -> `text-foreground`
    - Line 59: `text-slate-400` -> `text-muted-foreground`

- [ ] Task 9: Fix `components/KanbanBoard.tsx`
  - File: `components/KanbanBoard.tsx`
  - Action: Replace hardcoded color class:
    - Line 31: `text-slate-500` -> `text-muted-foreground`

- [ ] Task 10: Fix `components/TaskCard.tsx`
  - File: `components/TaskCard.tsx`
  - Action: Replace hardcoded color classes:
    - Line 43: `text-slate-900` -> `text-foreground`
    - Line 45: `text-slate-500` -> `text-muted-foreground`
    - Line 54: `bg-slate-100 text-slate-600` -> `bg-muted text-muted-foreground`
    - Line 63: `text-slate-400` -> `text-muted-foreground`
    - Line 64: `text-slate-400` -> `text-muted-foreground`
    - Line 96: `text-slate-500` -> `text-muted-foreground`

- [ ] Task 11: Fix `components/TaskInput.tsx`
  - File: `components/TaskInput.tsx`
  - Action: Replace hardcoded color classes:
    - Line 148: `text-slate-500` -> `text-muted-foreground`
    - Line 169: `text-slate-500` -> `text-muted-foreground`
    - Line 203: `text-slate-600` -> `text-muted-foreground`

- [ ] Task 12: Fix `components/TaskDetailSheet.tsx`
  - File: `components/TaskDetailSheet.tsx`
  - Action: Replace hardcoded color classes:
    - Line 67: `text-slate-500` -> `text-muted-foreground`
    - Lines 132, 136: `text-slate-400` -> `text-muted-foreground`
    - Lines 156, 165, 179, 189, 199, 209: `text-slate-500` -> `text-muted-foreground`
    - Lines 159, 182, 192, 202: `text-slate-700` -> `text-foreground`

- [ ] Task 13: Fix `components/ExecutionPlanTab.tsx`
  - File: `components/ExecutionPlanTab.tsx`
  - Action: Replace hardcoded color classes:
    - Line 28: `text-slate-300` -> `text-muted-foreground`
    - Line 35: `text-slate-400` -> `text-muted-foreground`
    - Line 54: `text-slate-500` -> `text-muted-foreground`
    - Line 72: `border-slate-200` -> `border-border`
    - Line 74: `text-slate-400` -> `text-muted-foreground`
    - Line 79: `text-slate-800` -> `text-foreground`
    - Line 81: `text-slate-500` -> `text-muted-foreground`

- [ ] Task 14: Fix `components/ThreadMessage.tsx`
  - File: `components/ThreadMessage.tsx`
  - Action: Replace hardcoded color classes:
    - Line 24: `bg-slate-50` -> `bg-muted`
    - Line 27: `bg-white` -> `bg-background`
    - Line 46: `text-slate-700` -> `text-foreground`
    - Line 54: `text-slate-400` -> `text-muted-foreground`
    - Line 66: `text-slate-600` -> `text-muted-foreground`

- [ ] Task 15: Update test files with new class names
  - Files: `components/ExecutionPlanTab.test.tsx`, `components/AgentSidebarItem.test.tsx`, `components/TaskDetailSheet.test.tsx`
  - Action: Update assertions that check for hardcoded class names:
    - `ExecutionPlanTab.test.tsx` line 109: `text-slate-300` -> `text-muted-foreground`
    - `ExecutionPlanTab.test.tsx` line 144: `border-slate-200` -> `border-border`
    - `AgentSidebarItem.test.tsx` line 111: `bg-slate-400` -> `bg-muted-foreground`
    - `TaskDetailSheet.test.tsx` line 211: `bg-white` -> `bg-background`
    - `TaskDetailSheet.test.tsx` line 235: `bg-slate-50` -> `bg-muted`

### Acceptance Criteria

- [ ] AC 1: Given the dashboard in light mode, when viewing any page, then all backgrounds use `bg-background` (white) and all text uses `text-foreground` / `text-muted-foreground` tokens — no hardcoded slate/white classes remain.
- [ ] AC 2: Given the dashboard in dark mode (via ThemeToggle), when viewing any page, then all components render with appropriate dark theme colors — no white backgrounds or dark-on-dark text.
- [ ] AC 3: Given the Kanban board with tasks in "Assigned" and "In Progress" columns, when viewing them side by side, then the status colors are visually distinct — Assigned uses cyan, In Progress uses blue.
- [ ] AC 4: Given the Kanban board in dark mode, when viewing task cards, then status color backgrounds use dark variants (e.g., `bg-violet-950`) with light text (e.g., `text-violet-300`), maintaining readability.
- [ ] AC 5: Given any component file in the `components/` directory (excluding `components/ui/`), when searching for `slate`, `bg-white`, `text-gray`, or `bg-gray`, then zero matches are found.
- [ ] AC 6: Given the existing test suite, when running `npm test`, then all tests pass with the updated class name assertions.

## Additional Context

### Dependencies

- No new dependencies needed — all infrastructure (next-themes, CSS variables, ThemeToggle) already exists
- Task 1 (STATUS_COLORS) should be done first since other components consume these values
- Tasks 2-14 are independent of each other and can be done in any order or in parallel
- Task 15 (tests) should be done last after all component changes

### Testing Strategy

- **Automated:** Run `npm test` to verify test files pass after class name updates
- **Manual — Light mode:** Toggle to light mode, navigate all views (Kanban, task detail, agent sidebar, activity feed), verify no visual regressions
- **Manual — Dark mode:** Toggle to dark mode, verify all components render with correct dark colors, no white backgrounds or unreadable text
- **Manual — Status colors:** Create tasks in different statuses, verify Assigned (cyan) and In Progress (blue) are visually distinct in both light and dark modes
- **Grep verification:** Run `grep -r "slate\|bg-white\|text-gray\|bg-gray" components/ --include="*.tsx" --exclude-dir=ui` and confirm zero matches (excluding `components/ui/`)

### Notes

- The sidebar component from shadcn/ui (`components/ui/sidebar.tsx`) is the gold standard reference for correct token usage
- `sidebar-*` tokens should be used inside Sidebar components (`AgentSidebar.tsx`, `AgentSidebarItem.tsx`) to match shadcn patterns; regular tokens (`bg-background`, `text-foreground`) for everything else
- The `dark:` prefix on status colors works because Tailwind config has `darkMode: ["selector", "class"]` and next-themes adds the `dark` class to `<html>`
