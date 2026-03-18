# Story 8.1: Reduce TaskInput Layout Shift

Status: ready-for-dev

## Story

As a **user**,
I want the task creation form to not "jump" when toggling supervision modes,
so that the experience feels smooth and predictable.

## Context

The `TaskInput` component conditionally renders the Eye/Zap supervision-mode button and the ChevronDown expand button using `{!isManual && (...)}` (lines 203-234 in `TaskInput.tsx`). Toggling between manual and AI mode removes these buttons from the DOM entirely, causing the toolbar to reflow and shrink. Similarly, the `CollapsibleContent` wrapping the agent/trust-level/reviewer options (lines 299-392) is conditionally rendered, causing a layout jump when toggled.

The fix replaces conditional rendering with CSS visibility: elements stay in the DOM but become invisible and non-interactive via `opacity-0 pointer-events-none` + `tabIndex={-1}`. The `CollapsibleContent` transition is smoothed using CSS `transition-all duration-200` (or Radix built-in animation data attributes) so expanding/collapsing does not cause a hard jump.

**No schema changes. No new dependencies.**

## Acceptance Criteria

1. **No layout reflow on mode toggle** -- Given the task input is visible, when the user clicks the Bot/User toggle to switch between AI and manual mode, then the toolbar width does not change and no elements shift position (the Eye/Zap button and ChevronDown button remain in the DOM but become invisible).

2. **No layout reflow on supervision toggle** -- Given the task input is in AI mode, when the user clicks the Eye/Zap button to toggle between autonomous and supervised, then no surrounding elements shift position.

3. **Hidden elements are not keyboard-focusable** -- Given the task input is in manual mode, when the user presses Tab to navigate through the form, then the hidden Eye/Zap button and ChevronDown button are skipped entirely (not reachable via keyboard).

4. **Smooth expand/collapse for options panel** -- Given the task input is in AI mode and the user clicks ChevronDown to expand options, then the CollapsibleContent expands with a smooth transition (no hard jump).

5. **Functional behavior unchanged** -- Given the task input is in AI mode with options expanded, when the user selects an agent, trust level, or reviewers, then the existing behavior (state updates, form submission) works identically to before.

## Tasks / Subtasks

- [ ] **Task 1: Replace conditional rendering of Eye/Zap button with CSS visibility** (AC: 1, 3)
  - [ ] 1.1 In `TaskInput.tsx`, locate the first `{!isManual && (...)}` block (lines 203-225) that wraps the supervision-mode toggle button (`<button>` with Eye/Zap icons).
  - [ ] 1.2 Remove the `{!isManual && (...)}` conditional wrapper. The `<button>` should always render in the DOM.
  - [ ] 1.3 Add conditional CSS classes to the button: when `isManual === true`, add `opacity-0 pointer-events-none` to the existing `className` string. When `isManual === false`, do not add these classes (button is fully visible and interactive).
  - [ ] 1.4 Add `tabIndex={isManual ? -1 : undefined}` to the button so it is removed from the tab order when hidden.
  - [ ] 1.5 Add `aria-hidden={isManual ? true : undefined}` for screen reader compliance.

- [ ] **Task 2: Replace conditional rendering of ChevronDown CollapsibleTrigger with CSS visibility** (AC: 1, 3)
  - [ ] 2.1 In `TaskInput.tsx`, locate the second `{!isManual && (...)}` block (lines 226-234) that wraps the `<CollapsibleTrigger>` with ChevronDown.
  - [ ] 2.2 Remove the `{!isManual && (...)}` conditional wrapper. The `<CollapsibleTrigger>` should always render in the DOM.
  - [ ] 2.3 On the inner `<Button>` inside `CollapsibleTrigger`, add conditional CSS classes: when `isManual === true`, add `opacity-0 pointer-events-none`.
  - [ ] 2.4 Add `tabIndex={isManual ? -1 : undefined}` to the `<Button>` so it is removed from the tab order when hidden.
  - [ ] 2.5 Add `aria-hidden={isManual ? true : undefined}` for screen reader compliance.
  - [ ] 2.6 Ensure that when switching to manual mode, `isExpanded` is already set to `false` (line 193 already does this -- verify it still works after the refactor).

- [ ] **Task 3: Replace conditional rendering of CollapsibleContent with CSS visibility** (AC: 1, 4)
  - [ ] 3.1 In `TaskInput.tsx`, locate the third `{!isManual && (...)}` block (lines 299-392) that wraps the `<CollapsibleContent>` containing agent/trust-level/reviewer fields.
  - [ ] 3.2 Remove the `{!isManual && (...)}` conditional wrapper. The `<CollapsibleContent>` should always render in the DOM.
  - [ ] 3.3 Note: when `isManual` is true and `isExpanded` is false (set on line 193), the `CollapsibleContent` from Radix will already be collapsed (height 0). The `Collapsible` parent uses `open={isExpanded}` which is set to `false` when switching to manual. So the content will be hidden naturally. However, we still need to ensure the content is not focusable when `isManual` is true AND the user somehow expands it (edge case).
  - [ ] 3.4 Add `transition-all duration-200` to the `CollapsibleContent`'s inner `<div>` (line 301, the `className="mt-2 p-3 border rounded-md space-y-3"` div) for smooth expand/collapse transitions.
  - [ ] 3.5 Alternative (preferred): Add Radix animation data attributes to the `CollapsibleContent` element itself. Radix Collapsible exposes `data-[state=open]` and `data-[state=closed]` attributes. Add classes: `data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0` to `CollapsibleContent`. This leverages the same `animate-in`/`animate-out` pattern already used throughout the project (see `dialog.tsx`, `dropdown-menu.tsx`, `sheet.tsx`).

- [ ] **Task 4: Add transition to the button toolbar for smooth opacity changes** (AC: 1, 2)
  - [ ] 4.1 Add `transition-opacity duration-200` to both the Eye/Zap button and ChevronDown button so the opacity change from 1 to 0 (and back) is animated rather than instantaneous.
  - [ ] 4.2 Verify the existing `transition-colors` class on the Eye/Zap button (line 213) does not conflict with `transition-opacity`. If it does, replace both with `transition-all duration-200` which covers colors, opacity, and transform.

- [ ] **Task 5: Verify no regressions and write tests** (AC: 1, 2, 3, 5)
  - [ ] 5.1 Manually verify in the browser: toggle AI/Manual mode rapidly -- the toolbar should not jump or change width.
  - [ ] 5.2 Manually verify: in AI mode, toggle autonomous/supervised -- no layout shift.
  - [ ] 5.3 Manually verify: in AI mode, expand/collapse options -- smooth transition.
  - [ ] 5.4 Manually verify: Tab through the form in manual mode -- Eye/Zap and ChevronDown buttons should be skipped.
  - [ ] 5.5 Manually verify: Create a task in AI mode with all options set (agent, trust level, reviewers) -- submission works correctly.
  - [ ] 5.6 Manually verify: Create a task in manual mode -- submission works correctly (isManual=true path).
  - [ ] 5.7 If `TaskInput.test.tsx` exists, update tests to account for the fact that Eye/Zap and ChevronDown buttons are always in the DOM (queries by role/label should still find them, but they should have `aria-hidden` when in manual mode).

## Dev Notes

### Code Locations (TaskInput.tsx)

**Three conditional blocks to refactor:**

1. **Lines 203-225** -- Eye/Zap supervision-mode button:
   ```tsx
   {!isManual && (
     <button type="button" aria-label={...} ...>
       {supervisionMode === "supervised" ? <Eye /> : <Zap />}
     </button>
   )}
   ```
   Replace with always-rendered button + conditional CSS.

2. **Lines 226-234** -- ChevronDown CollapsibleTrigger:
   ```tsx
   {!isManual && (
     <CollapsibleTrigger asChild>
       <Button variant="ghost" size="icon" aria-label="Toggle options">
         <ChevronDown ... />
       </Button>
     </CollapsibleTrigger>
   )}
   ```
   Replace with always-rendered trigger + conditional CSS.

3. **Lines 299-392** -- CollapsibleContent with agent/trust/reviewer options:
   ```tsx
   {!isManual && (
     <CollapsibleContent>
       <div className="mt-2 p-3 border rounded-md space-y-3">
         {/* Agent select, Trust level, Reviewers */}
       </div>
     </CollapsibleContent>
   )}
   ```
   Replace with always-rendered content (Radix handles collapse via `open` prop).

### CSS Pattern for Hiding

```tsx
// Pattern to use for hidden-but-in-DOM elements
className={`... ${isManual ? "opacity-0 pointer-events-none" : ""}`}
tabIndex={isManual ? -1 : undefined}
aria-hidden={isManual ? true : undefined}
```

### Radix Collapsible Animation Pattern

The project already uses Radix `data-[state=*]` animation classes extensively (see `dialog.tsx` line 24, `dropdown-menu.tsx` line 50, `sheet.tsx` line 34). Apply the same pattern to `CollapsibleContent`:

```tsx
<CollapsibleContent className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 overflow-hidden transition-all">
```

Note: Radix Collapsible also provides `--radix-collapsible-content-height` CSS variable for height animation. The Tailwind config likely already includes `animate-in`/`animate-out` keyframes from `tailwindcss-animate` plugin.

### Important: `motion` Package Available But Not Needed

The project has `motion` v12 (successor to `framer-motion`) installed, but the Radix data-attribute animation pattern is simpler, more consistent with the existing codebase, and does not require importing additional components. Prefer the CSS/Radix approach.

### Common LLM Developer Mistakes to Avoid

1. **DO NOT just add `display: none` or `visibility: hidden`** -- These still cause layout shift when the element appears/disappears (display: none removes from layout flow). Use `opacity-0 pointer-events-none` which keeps the element in layout flow with its full dimensions.

2. **DO NOT forget `tabIndex={-1}`** -- Without this, keyboard users can Tab to invisible buttons, which is a confusing accessibility bug.

3. **DO NOT forget `aria-hidden`** -- Screen readers will announce invisible buttons unless `aria-hidden` is set.

4. **DO NOT change the manual-mode toggle behavior** (lines 184-194) -- The existing `setIsExpanded(false)` on manual toggle is critical. Without it, the CollapsibleContent would stay expanded (visible) even though the trigger is hidden.

5. **DO NOT add `transition` classes to the parent `<div className="flex gap-2">` container** -- Transitions on flex containers can cause jank. Apply transitions to the individual elements being animated.

6. **DO NOT wrap CollapsibleContent in an extra div for animation** -- Radix Collapsible already handles the open/closed state. Adding extra wrappers can break the Radix state management.

### Project Structure Notes

- Component: `dashboard/components/TaskInput.tsx` (only file to modify)
- UI primitives: `dashboard/components/ui/collapsible.tsx` (Radix wrapper, read-only)
- Animation utilities already in Tailwind config via `tailwindcss-animate` plugin

### References

- [Source: `dashboard/components/TaskInput.tsx`] -- The component being modified
- [Source: `dashboard/components/ui/collapsible.tsx`] -- Radix Collapsible wrapper
- [Source: `dashboard/components/ui/dialog.tsx`] -- Example of `animate-in`/`animate-out` pattern
- [Source: `dashboard/components/ui/dropdown-menu.tsx`] -- Example of `data-[state=*]` animation classes
- [Radix Collapsible docs] -- `data-[state=open]` / `data-[state=closed]` attributes

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
