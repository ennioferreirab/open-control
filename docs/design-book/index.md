# Open Control — Design Book

> **Direction**: Clean Command
> **Reference**: Notion (clarity, typography, breathing room) + dark-first
> **Personality**: Professional & Reliable
> **Palette**: Neutral pure
> **Density**: Comfortable
> **Font**: Inter

---

## Design Principles

1. **Clarity over decoration** — Every element earns its place. No ornamental borders, no gratuitous gradients, no visual noise. If removing an element doesn't hurt comprehension, remove it.

2. **Tokens, not values** — Never hardcode a color, size, or duration. Everything references a token. When the system changes, everything changes together.

3. **Status at a glance** — Color and shape communicate state instantly. A user should understand a task's state in under 1 second without reading text.

4. **Dark mode is primary** — The dark theme is the main experience. Light mode is equally supported but dark is the default and the one we optimize first.

5. **Accessible by default** — Keyboard navigation, screen reader support, focus indicators, and reduced motion are not afterthoughts. They're built in from the start.

---

## Documents

| Document | What it covers |
|----------|---------------|
| [tokens.md](tokens.md) | All design tokens: colors, typography, spacing, shadows, radius, motion |
| [components/atoms.md](components/atoms.md) | Button, Badge, Input, Avatar, Separator, Toggle, Checkbox |
| [components/molecules.md](components/molecules.md) | TagChip, StatusBadge, InlineConfirm, TerminalHeader, SearchBar |
| [components/organisms.md](components/organisms.md) | StatusCard, TaskDetailSheet, AgentConfigSheet, SquadDetail |
| [layout.md](layout.md) | Grid system, breakpoints, overlay sizes, card anatomy |
| [motion.md](motion.md) | Animation patterns, durations, easing, accessibility |
| [accessibility.md](accessibility.md) | WCAG AA, focus management, ARIA, keyboard navigation |
| [dark-mode.md](dark-mode.md) | Dark mode rules, current bugs to fix, surface hierarchy |
| [migration-guide.md](migration-guide.md) | Implementation wave plan with dependencies |

---

## Quick Reference

### Color Usage

| Purpose | Token | Dark | Light |
|---------|-------|------|-------|
| Page background | `--background` | `#111111` | `#ffffff` |
| Cards/panels | `--card` | `#191919` | `#f9f9f9` |
| Primary CTA | `--primary` | `#2383e2` | `#2383e2` |
| Approve/success | `--success` | `#2ea043` | `#1a7f37` |
| Review/warning | `--warning` | `#d29922` | `#9a6700` |
| Danger/delete | `--destructive` | `#da3633` | `#cf222e` |
| Text | `--foreground` | `#eeeeee` | `#1a1a1a` |
| Muted text | `--muted-foreground` | `#888888` | `#6b6b6b` |
| Borders | `--border` | `#2a2a2a` | `#e5e5e5` |

### Typography Scale

| Level | Size | Weight | Use |
|-------|------|--------|-----|
| Display | 28px | Bold (700) | Hero headings (rare) |
| Title | 22px | Semibold (600) | Page titles |
| Heading | 16px | Semibold (600) | Section headers, column titles |
| Body | 15px | Normal (400) | Default text, descriptions |
| Small | 13px | Normal (400) | Secondary info, metadata |
| Micro | 11px | Medium (500) | Timestamps, labels, badges |

### Spacing (4px grid)

| Token | Value | Common use |
|-------|-------|-----------|
| `gap-2` | 8px | Between inline items |
| `gap-3` | 12px | Between card elements |
| `gap-4` | 16px | Between sections |
| `p-3` | 12px | Card internal padding |
| `p-4` | 16px | Panel/section padding |
| `px-6` | 24px | Sheet content horizontal padding |
