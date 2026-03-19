# Motion Guidelines

## Principles

1. **Purposeful** — Every animation communicates a state change. If it's decorative, remove it.
2. **Fast** — 200ms default. Users should never wait for an animation to finish before acting.
3. **Asymmetric** — Entrances slightly slower (300ms) than exits (200ms). Things leaving should get out of the way.
4. **Respectful** — Always honor `prefers-reduced-motion`. Use the `useReducedMotion()` hook.
5. **Consistent** — Same interaction type = same animation everywhere in the app.

---

## Pattern Library

| Pattern | Duration | Easing | Properties | When to Use |
|---------|----------|--------|------------|-------------|
| Color change | `--duration-fast` (100ms) | `--easing-default` | background, color, border-color | Hover/focus states on buttons, icons, links |
| Fade in | `--duration-normal` (200ms) | `--easing-out` | opacity 0→1 | List items appearing, messages, feed items |
| Fade out | `--duration-fast` (100ms) | `--easing-in` | opacity 1→0 | Items being removed |
| Slide in | `--duration-slow` (300ms) | `--easing-out` | translateX/Y | Sheets opening, panels appearing |
| Slide out | `--duration-normal` (200ms) | `--easing-in` | translateX/Y | Sheets closing |
| Height reveal | `--duration-normal` (200ms) | `--easing-out` | height 0→auto, opacity 0→1 | Expand/collapse, inline confirms |
| Layout shift | `--duration-slow` (300ms) | spring | layout (auto) | Card reorder in kanban, drag-drop |
| Scale press | `--duration-fast` (100ms) | `--easing-spring` | scale(0.98) | Button active state feedback |
| Pulse | 600ms | ease-in-out | scale + box-shadow | Notification count, live status dots |
| Spin | infinite | linear | rotate(360deg) | Loading spinners (Loader2) |

---

## Implementation Rules

### Tailwind Transitions
```html
<!-- Hover color change -->
<button class="transition-colors duration-fast">

<!-- Opacity show/hide -->
<div class="transition-opacity duration-normal">

<!-- Multi-property (panels, width changes) -->
<div class="transition-all duration-slow">
```

### Motion Library (layout animations)
```tsx
// Card with layout animation
<motion.div
  layoutId={task._id}
  layout={!isDragging}
  transition={{ duration: shouldReduceMotion ? 0 : 0.3, type: "spring" }}
/>

// Conditional render WITH exit animation
<AnimatePresence>
  {isOpen && (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
    />
  )}
</AnimatePresence>
```

### Reduced Motion
```tsx
const shouldReduceMotion = useReducedMotion();

// In transition props
transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}

// In Tailwind
className="motion-safe:animate-pulse"
```

---

## Critical Fixes from Audit

1. **AnimatePresence missing** — Add to: InlineRejection, KanbanColumn (clear confirm), StepCard (delete confirm), TaskCard (delete confirm)
2. **Hardcoded durations** — Replace `{ duration: 0.15 }`, `{ duration: 0.2 }`, `{ duration: 0.3 }` with token-based values
3. **No spring animations** — Switch layout transitions from linear to `type: "spring"` for natural feel
4. **Inconsistent easing** — Some use `ease-linear` (sidebar), some `ease-in-out` (sheets). Standardize per pattern table above.
