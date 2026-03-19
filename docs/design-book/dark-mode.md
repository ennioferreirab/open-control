# Dark Mode

Dark mode is the primary experience. Light mode is equally supported but dark comes first.

## Surface Hierarchy

Depth is communicated through subtle brightness steps, not shadows.

| Layer | Dark | Light | Use |
|-------|------|-------|-----|
| Canvas | `#111111` | `#ffffff` | Page background |
| Surface | `#191919` | `#f9f9f9` | Cards, columns, panels |
| Raised | `#222222` | `#ffffff` | Popovers, dropdowns, tooltips |
| Overlay | `#191919` + `--border` | `#ffffff` + `--shadow-lg` | Sheets, dialogs |
| Inset | `#0d0d0d` | `#f0f0f0` | Sunken areas, input backgrounds |

Each dark layer is ~2% lighter than the one below.

## Rules

1. **Borders replace shadows** — In dark mode, use `border-[--border]` instead of shadows for depth. Shadows are barely visible on dark backgrounds.
2. **Text hierarchy through opacity** — Primary (#eee), secondary (#888), tertiary (#555). Not through color hue.
3. **Status colors are brighter** — Dark mode status colors should be ~10-15% brighter than light mode equivalents for readability.
4. **Images and icons** — SVG icons inherit `currentColor`. No filter/invert hacks.
5. **Focus rings** — Same blue (`--ring: #2383e2`) in both modes. High contrast against both black and white.

## Bugs to Fix (from Audit)

| Component | Issue | Fix |
|-----------|-------|-----|
| `ThreadMessage.tsx` | Uses `bg-blue-50`, `bg-green-50`, `bg-red-50` without `dark:` variants | Replace with `bg-[hsl(var(--status-*))]` using muted status tokens |
| `TaskDetailHeader.tsx` | Error banners use `bg-red-50 border-red-200 text-red-800` | Replace with `bg-destructive/10 border-destructive/20 text-destructive` |
| `CronJobsModal.tsx` | Status badges use hardcoded `bg-green-50`, `bg-red-50` | Use `StatusBadge` component with `--status-*` tokens |
| `AgentSidebarItem.tsx` | Agent glow shadows use hardcoded `rgba()` | Use `shadow-[0_0_6px_hsl(var(--status-progress)/0.5)]` |
| `InteractiveTerminalPanel.tsx` + `AgentTerminal.tsx` | Duplicated xterm theme with hardcoded colors | Extract shared `TERMINAL_THEME` constant |

## Terminal Theme (Exception)

The terminal/live panels use a fixed dark theme regardless of app mode. This is intentional — terminals should always be dark.

```ts
const TERMINAL_THEME = {
  background: '#09090b',  // zinc-950
  foreground: '#f4f4f5',  // zinc-100
  cursor: '#f4f4f5',
  selection: '#27272a',   // zinc-800
};
```
