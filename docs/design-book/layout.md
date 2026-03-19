# Layout System

## Page Structure

```
┌─────────────────────────────────────────────────────────────┐
│ Header (56px, border-b)                                     │
├────────┬────────────────────────────────────┬───────────────┤
│Sidebar │ Main Content                       │Activity Panel │
│ 240px  │ flex-1                             │ 280-420px     │
│        │ ┌──────────────────────────────┐   │               │
│        │ │ Task Input (border-b)        │   │               │
│        │ ├──────────────────────────────┤   │               │
│        │ │ Kanban Board (5 columns)     │   │               │
│        │ │ px-4 py-4                    │   │               │
│        │ └──────────────────────────────┘   │               │
├────────┴────────────────────────────────────┴───────────────┤
│ [Overlay: TaskDetailSheet at 50vw from right]               │
└─────────────────────────────────────────────────────────────┘
```

## Dimensions

| Element | Token | Value |
|---------|-------|-------|
| Header height | `--layout-header` | 56px |
| Sidebar expanded | `--layout-sidebar` | 240px (15rem) |
| Sidebar collapsed | `--layout-sidebar-collapsed` | 64px (4rem) |
| Sidebar mobile | `--layout-sidebar-mobile` | 288px (18rem) |
| Activity panel (feed) | `--layout-activity` | 280px |
| Activity panel (chat) | `--layout-activity-chat` | 420px |
| Content max-width | `--layout-content-max` | 1400px |
| Kanban column min-width | — | 240px |
| Kanban column mobile | — | 85vw snap |

## Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|---------------|
| `sm` | 640px | Sheets get explicit widths. Dialogs size up. |
| `md` | **768px** | Sidebar toggles. Kanban switches from h-scroll to 5-col grid. Activity panel inline. Header shows full title. |
| `lg` | 1024px | Thread/content max-widths increase. |
| `xl` | 1280px | Sidebar auto-opens. Widest content areas. |

**Mobile (< md)**: Single column, sidebar hidden behind hamburger, activity panel fullscreen modal, kanban horizontal scroll with snap.

## Overlay Size System

| Category | Width | Use Cases |
|----------|-------|-----------|
| **Narrow** | 400px | Tags panel, simple config |
| **Medium** | 480px | Agent config, Done tasks, Trash bin |
| **Wide** | 600px | Settings panel |
| **XL** | 50vw (min 600px) | Task detail sheet |
| **Full** | 96vw / max-w-6xl | Squad detail, workflow canvas |

**All overlays**: `p-0` on SheetContent, then `px-6 py-4` on internal scroll areas.

## Card Anatomy

```
┌───────────────────────────────────────┐
│▌ Header                               │  ← 3px accent border (left)
│▌  [Title — text-body semibold]  ☆ 👤 ▾│  ← action icons right-aligned
│▌                                       │
│▌ Body                                  │
│▌  [Description — text-small, 2-line]   │
│▌                                       │
│▌ Tags                                  │
│▌  [chip] [chip]                        │  ← TagChip components
│▌                                       │
│▌ Footer                                │
│▌  [StatusBadge]  [3/5 steps]    🗑    │  ← status + metadata + delete
└───────────────────────────────────────┘
```

**Card tokens**:
- Background: `--card`
- Border: `--border`, left accent `--status-*` (3px)
- Radius: `--radius-lg` (8px)
- Padding: `p-3` (12px)
- Gap between elements: `gap-2` (8px)
- Hover: `shadow-sm` + border lightens slightly
- Title: `--text-body` (15px) / semibold
- Description: `--text-small` (13px) / normal / `--muted-foreground`
- Max 2 lines clamp on description

## Kanban Column

- Header: Column name (`--text-heading`, 16px semibold) + count badge + colored dot
- Gap between cards: `gap-3` (12px)
- Column background: `--card` with 40% opacity on muted
- Mobile: `w-[85vw]` with `snap-center`
- 5 columns at `md+`: equal width grid
