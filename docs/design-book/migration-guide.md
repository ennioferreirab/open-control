# Migration Guide

Implementation plan to apply the new design system. Each wave is a separate branch with before/after screenshots for review.

---

## Pre-requisites

1. Install Inter font: `npm install @fontsource-variable/inter` or add via Google Fonts
2. Keep Geist Mono for code/terminal contexts
3. All changes on `feat/design-system` branch (or per-wave branches)

---

## Wave 1 — Foundation (Low Risk)

**What changes**: CSS variables, Tailwind config, font setup. No component code changes.

| File | Change |
|------|--------|
| `dashboard/app/globals.css` | Replace all CSS variables with new token values. Dark-first (`:root` = dark). Add `.light` class. Add `--success`, `--warning`, `--info`, all `--status-*`, all `--tag-*` tokens. |
| `dashboard/tailwind.config.ts` | Add `success`, `warning`, `info` to colors. Add `status-*` and `tag-*` color mappings. Update `--radius` default to 8px. |
| `dashboard/app/layout.tsx` | Switch font from Geist to Inter for sans. Keep Geist Mono. |
| `dashboard/lib/constants.ts` | Refactor `STATUS_COLORS` and `TAG_COLORS` to use new CSS variable tokens instead of Tailwind color classes. |

**Test**: Visual regression only — everything should look slightly different but nothing should break.

---

## Wave 2 — Atoms (Low Risk)

**What changes**: Base UI components get new variants and sizing.

| File | Change |
|------|--------|
| `components/ui/button.tsx` | Add `success` and `warning` variants. Remove `link` (unused). Update default radius to `rounded-lg`. |
| `components/ui/badge.tsx` | Add `success`, `warning`, `info` variants. Add `status` variant that reads from `--status-*` tokens. |
| `components/ui/input.tsx` | Add `sm`/`lg` size variants via CVA. Add error state (`aria-invalid` + red border). |
| `components/ui/textarea.tsx` | Match input sizing updates. |
| `components/ui/avatar.tsx` | Add size scale: `xs` (24px), `sm` (32px), `md` (40px), `lg` (48px), `xl` (64px). |

**Test**: Storybook-style check of each variant. Run `make validate`.

---

## Wave 3 — Molecules (Medium Risk)

**What changes**: Extract duplicated patterns into shared components.

| New Component | Replaces Code In | Notes |
|--------------|-----------------|-------|
| `components/TagChip.tsx` | TaskCard, TaskDetailHeader, TaskDetailConfigTab, TaskInput, SearchBar, TagsPanel | Uses `--tag-*` tokens. Props: `color`, `label`, `onRemove?`, `size?` |
| `components/StatusBadge.tsx` | TaskCard, StepCard, FlowStepNode, KanbanColumn, DoneTasksSheet | Uses `--status-*` tokens. Props: `status`, `size?` |
| `components/InlineConfirm.tsx` | TaskCard, StepCard, KanbanColumn | Wraps `AnimatePresence` + `motion.div`. Props: `open`, `onConfirm`, `onCancel`, `message?` |
| `components/TerminalHeader.tsx` | InteractiveTerminalPanel, TerminalPanel, ProviderLiveChatPanel, AgentActivityFeed | Props: `agentName`, `provider`, `status`, `sessionId?` |

**Migration strategy**: Create new component → update one usage → verify → update remaining usages.

**Test**: Each file that imported the old pattern should now import the shared component. Run `make validate` + `make typecheck`.

---

## Wave 4 — Layout (Medium Risk)

**What changes**: Structural spacing and dimensions.

| File | Change |
|------|--------|
| `components/DashboardLayout.tsx` | Header h-[56px] (from 60px). Apply new spacing tokens. Update title typography to `--text-title`. |
| `components/KanbanColumn.tsx` | Update card gap to `gap-3`. Column header typography to `--text-heading`. |
| `features/tasks/components/TaskDetailSheet.tsx` | Standardize internal padding to `px-6 py-4`. Tab spacing. |
| `features/agents/components/AgentSidebar.tsx` | Apply sidebar tokens. Agent item spacing. |
| `features/activity/components/ActivityFeedPanel.tsx` | Width tokens. Event spacing. |

**Test**: Visual check on all breakpoints (mobile, tablet, desktop). `make validate`.

---

## Wave 5 — Organisms (High Risk)

**What changes**: Major feature components use new tokens, molecules, and layout.

| File | Change |
|------|--------|
| `features/tasks/components/TaskCard.tsx` | Use `StatusBadge`, `TagChip`, `InlineConfirm`. Apply new radius/spacing. Replace hardcoded status colors. |
| `features/tasks/components/StepCard.tsx` | Same as TaskCard. Consider shared `StatusCard` base. |
| `features/tasks/components/TaskDetailHeader.tsx` | New typography scale. Use `StatusBadge`. Replace green button overrides with `variant="success"`. Fix amber/orange button overrides with `variant="warning"`. |
| `features/agents/components/AgentConfigSheet.tsx` | New form layout, input sizes, spacing. |
| `features/agents/components/SquadDetailSheet.tsx` | Agent cards with new avatar sizes. Workflow canvas styling. |
| `features/thread/components/ThreadMessage.tsx` | Fix dark mode colors. Use semantic tokens for message type backgrounds. |

**Test**: Open every major view and verify. Run full test suite. Manual testing on both themes.

---

## Wave 6 — Polish (Low Risk)

**What changes**: Animations, accessibility, final dark mode fixes.

| Area | Change |
|------|--------|
| **AnimatePresence** | Wrap conditional `motion.div` in InlineRejection, KanbanColumn, StepCard, TaskCard |
| **Motion tokens** | Replace hardcoded durations (150ms, 200ms, 300ms) with `--duration-*` tokens |
| **Focus management** | Add `focus-visible:ring-2 focus-visible:ring-ring` to all interactive elements |
| **Keyboard** | Ensure all clickable divs have `tabIndex={0}`, `role="button"`, `onKeyDown` |
| **ARIA** | Add `aria-label` to all icon-only buttons (6+ identified in audit) |
| **Dark mode** | Fix ThreadMessage light-only colors. Fix TaskDetailHeader error banners. Fix CronJobsModal status badges. |
| **Reduced motion** | Verify `useReducedMotion` in all animation components |
| **Contrast** | Audit all text/bg combinations for WCAG AA (4.5:1 text, 3:1 UI) |

**Test**: Lighthouse accessibility audit. Keyboard-only navigation test. `prefers-reduced-motion` test.

---

## Rollback Plan

Each wave is a separate branch. If a wave causes issues:
1. Revert the branch
2. Fix the issue
3. Re-apply

Waves 1-2 are safe to merge independently. Waves 3-5 depend on Wave 1-2 being merged. Wave 6 can be done anytime after Wave 3.

---

## Definition of Done (per wave)

- [ ] All changes use design tokens (no hardcoded values)
- [ ] `make validate` passes
- [ ] `make lint && make typecheck` passes
- [ ] Before/after screenshots captured
- [ ] Both dark and light mode verified
- [ ] No visual regressions in other components
