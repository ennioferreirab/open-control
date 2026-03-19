# Accessibility

Target: WCAG 2.1 AA compliance.

## Color Contrast

| Element | Minimum Ratio | Standard |
|---------|--------------|----------|
| Body text on background | 4.5:1 | AA |
| Large text (18px+ bold, 24px+ normal) | 3:1 | AA |
| UI components (borders, icons) | 3:1 | AA |
| Focus indicators | 3:1 | AA |

### Verification

All token combinations must pass contrast checks:
- `--foreground` on `--background`: must be ≥ 4.5:1
- `--muted-foreground` on `--background`: must be ≥ 4.5:1
- `--primary-foreground` on `--primary`: must be ≥ 4.5:1
- `--success-foreground` on `--success`: must be ≥ 4.5:1
- Status foreground on status muted background: must be ≥ 4.5:1

## Focus Management

Every interactive element must have a visible focus indicator:

```css
focus-visible:outline-none
focus-visible:ring-2
focus-visible:ring-[--ring]
focus-visible:ring-offset-2
focus-visible:ring-offset-[--background]
```

## Keyboard Navigation

| Element | Required Keys |
|---------|--------------|
| Buttons | Enter, Space |
| Links | Enter |
| Tabs | Arrow Left/Right, Home, End |
| Dialogs | Escape to close, trap focus inside |
| Sheets | Escape to close |
| Dropdowns | Arrow Up/Down, Enter to select, Escape to close |
| Kanban cards | Enter to open detail |

## Fixes from Audit

| Issue | Location | Fix |
|-------|----------|-----|
| Icon SVGs with `onClick` but no button wrapper | TaskCard (Star, Trash2), StepCard (Trash2), CompactFavoriteCard (Star), FlowStepNode (circles) | Wrap in `<button>` with `aria-label` |
| Clickable divs without keyboard support | CompactFavoriteCard, TaskCard, TaskDetailFilesTab, ArtifactRenderer | Add `role="button"`, `tabIndex={0}`, `onKeyDown` |
| Missing `focus-visible` in app code | Only 7 instances outside UI primitives | Add to all custom interactive elements |
| Missing `active:` feedback | Only 4 instances in app | Add `active:scale-[0.98]` or `active:opacity-80` to buttons |
| Zero `role="button"` usage | Entire codebase | Add where non-button elements are clickable |

## Screen Reader

- All icon-only buttons must have `aria-label`
- Status badges should have `aria-label` describing the status (not just color)
- Live regions (`aria-live="polite"`) for: gateway status changes, task status transitions, activity feed updates
- Sheet/Dialog titles: always present (use `VisuallyHidden` if needed)

## Reduced Motion

```tsx
// Hook-based
const shouldReduceMotion = useReducedMotion();
transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}

// CSS-based
className="motion-safe:animate-pulse"
className="motion-reduce:transition-none"
```

All `motion.div` components must respect reduced motion. All `animate-*` classes should be prefixed with `motion-safe:`.
