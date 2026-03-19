# Mission Control — Design Inventory (Dossie Completo)

> Generated: 2026-03-18
> Branch: feat/design-audit
> Screenshots: `docs/design-audit/screenshots/`

---

## Table of Contents

1. [Design System & Theme Tokens](#1-design-system--theme-tokens)
2. [Typography](#2-typography)
3. [shadcn/ui Component Library](#3-shadcnui-component-library)
4. [Icon Inventory](#4-icon-inventory)
5. [Button & Badge Usage](#5-button--badge-usage)
6. [Form Elements](#6-form-elements)
7. [Layout Architecture](#7-layout-architecture)
8. [Sheets & Modals](#8-sheets--modals)
9. [Spacing Patterns](#9-spacing-patterns)
10. [Animations & Transitions](#10-animations--transitions)
11. [Status Color System](#11-status-color-system)
12. [Custom Feature Components](#12-custom-feature-components)
13. [Issues & Inconsistencies](#13-issues--inconsistencies)

---

## 1. Design System & Theme Tokens

**Base palette:** shadcn/ui "Stone" (warm neutrals, HSL hue ~20-24).
**Dark mode:** `["selector", "class"]` via `next-themes`.

### Core Tokens

| Token | Light (Hex) | Dark (Hex) | Usage |
|-------|-------------|------------|-------|
| `--background` | `#ffffff` | `#0c0a09` | Page background |
| `--foreground` | `#0c0a09` | `#fafaf9` | Default text |
| `--card` / `--card-foreground` | `#ffffff` / `#0c0a09` | `#0c0a09` / `#fafaf9` | Card surfaces |
| `--popover` / `--popover-foreground` | `#ffffff` / `#0c0a09` | `#0c0a09` / `#fafaf9` | Popover surfaces |
| `--primary` / `--primary-foreground` | `#1c1917` / `#fafaf9` | `#fafaf9` / `#1c1917` | Primary actions |
| `--secondary` / `--secondary-foreground` | `#f5f5f4` / `#1c1917` | `#292524` / `#fafaf9` | Secondary surfaces |
| `--muted` / `--muted-foreground` | `#f5f5f4` / `#78716c` | `#292524` / `#a8a29e` | Muted text/bg |
| `--accent` / `--accent-foreground` | `#f5f5f4` / `#1c1917` | `#292524` / `#fafaf9` | Accent hover states |
| `--destructive` / `--destructive-foreground` | `#ef4444` / `#fafaf9` | `#7f1d1d` / `#fafaf9` | Destructive actions |
| `--border` | `#e7e5e4` | `#292524` | Borders |
| `--input` | `#e7e5e4` | `#292524` | Input borders |
| `--ring` | `#0c0a09` | `#d6d3d1` | Focus rings |

### Sidebar Tokens

| Token | Light (Hex) | Dark (Hex) |
|-------|-------------|------------|
| `--sidebar-background` | `#fafafa` | `#18181b` |
| `--sidebar-foreground` | `#3f3f46` | `#f4f4f5` |
| `--sidebar-primary` | `#18181b` | `#1d62d5` |
| `--sidebar-accent` | `#f4f4f5` | `#272729` |
| `--sidebar-border` | `#e4e4e7` | `#272729` |
| `--sidebar-ring` | `#3b82f6` | `#3b82f6` |

### Chart Tokens

| Token | Light (Hex) | Dark (Hex) |
|-------|-------------|------------|
| `--chart-1` | `#e2713a` | `#2663d9` |
| `--chart-2` | `#2a9d8f` | `#2eb88a` |
| `--chart-3` | `#264f63` | `#e09333` |
| `--chart-4` | `#e5c462` | `#a855cc` |
| `--chart-5` | `#f0935c` | `#d93073` |

### Border Radius

| Token | Value |
|-------|-------|
| `lg` | `0.5rem` (8px) |
| `md` | `0.375rem` (6px) |
| `sm` | `0.125rem` (4px) |

---

## 2. Typography

### Fonts

| Font | Variable | Usage |
|------|----------|-------|
| **Geist** (Google Fonts) | `--font-geist-sans` | Primary sans-serif |
| **Geist Mono** (Google Fonts) | `--font-geist-mono` | Code/monospace |

### Font Size Distribution

| Class | Size | Occurrences | % of total |
|-------|------|-------------|------------|
| `text-xs` | 12px | **359** (70 files) | 61% |
| `text-sm` | 14px | **207** (65 files) | 35% |
| `text-base` | 16px | 9 | 1.5% |
| `text-lg` | 18px | 17 | 2.9% |
| `text-xl` | 20px | 2 | 0.3% |
| `text-2xl` | 24px | 1 | 0.2% |
| `text-3xl+` | 30px+ | 0 | 0% |

**96% of text is `text-xs` or `text-sm`** — the UI is very compact.

### Font Weight Distribution

| Class | Weight | Occurrences | % |
|-------|--------|-------------|---|
| `font-medium` | 500 | **165** (55 files) | 73% |
| `font-semibold` | 600 | 53 (34 files) | 23% |
| `font-normal` | 400 | 6 (2 files) | 3% |
| `font-bold` | 700 | 3 (3 files) | 1% |

### Monospace Usage

`font-mono`: 40 occurrences across 19 files (terminal, code blocks, timestamps).

---

## 3. shadcn/ui Component Library

**24 components** in `dashboard/components/ui/`.

### Components with CVA Variants

| Component | Variants | Sizes | Notes |
|-----------|----------|-------|-------|
| **Button** | default, destructive, outline, secondary, ghost, link | default (h-9), sm (h-8), lg (h-10), icon (h-9 w-9) | Most used component |
| **Badge** | default, secondary, destructive, outline | — | `destructive` never used |
| **Sheet** | top, bottom, left, right | — | Default: right |
| **Toggle** | default, outline | default (h-9), sm (h-8), lg (h-10) | |
| **Sidebar MenuButton** | default, outline | default (h-8), sm (h-7), lg (h-12) | |

### All Components

| Component | Radix Primitive | Has Variants |
|-----------|----------------|--------------|
| AlertDialog | react-alert-dialog | No |
| Avatar | react-avatar | No |
| Badge | — | Yes (4) |
| Button | react-slot | Yes (6+4) |
| Card | — | No |
| Checkbox | react-checkbox | No |
| Collapsible | react-collapsible | No |
| Dialog | react-dialog | No |
| DropdownMenu | react-dropdown-menu | No |
| Input | — | No |
| Label | react-label | No |
| Popover | react-popover | No |
| ScrollArea | react-scroll-area | No |
| Select | react-select | No |
| Separator | react-separator | No |
| Sheet | react-dialog | Yes (4 sides) |
| Sidebar | react-slot | Yes (2+3) |
| Skeleton | — | No |
| Switch | react-switch | No |
| Tabs | react-tabs | No |
| Textarea | — | No |
| Toggle | react-toggle | Yes (2+3) |
| ToggleGroup | react-toggle-group | Inherited |
| Tooltip | react-tooltip | No |

---

## 4. Icon Inventory

**58 unique icons** from `lucide-react`.

### Most Used (>5 files)

| Icon | Files | Primary Use |
|------|-------|-------------|
| `Trash2` | 14 | Delete actions |
| `X` | 14 | Close/dismiss |
| `Loader2` | 9 | Loading spinners |
| `ChevronDown` | 9 | Expand/collapse |
| `Check` | 8 | Confirm/select |
| `Plus` | 8 | Add/create |
| `Paperclip` | 7 | File attachments |
| `User` | 6 | Agent/person |
| `Pencil` | 5 | Edit |

### By Category

| Category | Icons | Count |
|----------|-------|-------|
| **Actions** | Check, Copy, Download, Eraser, Pencil, Plus, Minus, Search, Send, SendHorizontal, SlidersHorizontal, Trash2, Undo2, X, Maximize2 | 15 |
| **Navigation** | ArrowLeft, ArrowRight, ChevronDown/Up/Left/Right, PanelLeft, PanelRightClose/Open | 9 |
| **Status** | Activity, AlertTriangle, CheckCircle, CheckCircle2, Circle, CircleDot, XCircle, Loader2, Info | 9 |
| **Objects** | Bot, File, FileCode, FileText, Image, Paperclip, User, Users | 8 |
| **Security** | Lock, Shield, Unlock | 3 |
| **Time** | Clock, History | 2 |
| **Data** | ExternalLink, GitMerge, List, ListChecks | 4 |
| **Media** | Pause, Play, Square | 3 |
| **Settings** | Settings, Settings2, Tag, Terminal | 4 |
| **Misc** | RefreshCw, RotateCcw, Star, MessageCircle | 4 |

### Redundancies

- `CheckCircle` + `CheckCircle2` (similar purpose)
- `Send` + `SendHorizontal` (same concept)
- `Settings` + `Settings2` (same concept)
- `RefreshCw` + `RotateCcw` (both used for retry/refresh)

---

## 5. Button & Badge Usage

### Button: 136 instances

**By variant:**

| Variant | Count | Notes |
|---------|-------|-------|
| default | ~95 | Many overridden with custom green/amber colors |
| outline | 10 | Download, cancel, retry |
| destructive | 9 | Deny, confirm delete |
| ghost | 5 | Cancel forms, collapse |
| secondary | 5 | View toggles, resume |
| link | **0** | Defined but never used |

**By size:**

| Size | Count | Notes |
|------|-------|-------|
| default | ~78 | Form submits, dialog actions |
| icon | ~30 | Send, attach, close, zoom |
| sm | ~26 | Inline task actions |
| lg | 5 | Sidebar items only |

**Custom color overrides (~12+ instances):**
- `bg-green-500/600 hover:bg-green-600/700 text-white` — Approve, Resume, Start
- `border-amber-500 text-amber-700 hover:bg-amber-50` — Retry
- `border-orange-400 text-orange-700 hover:bg-orange-50` — Pause
- `bg-emerald-500 text-zinc-950` — Terminal Done
- Missing: a `success`/`positive` variant would eliminate these overrides

### Badge: 44 instances

| Variant | Count | Notes |
|---------|-------|-------|
| default | ~26 | Status, labels |
| secondary | 11 | Counts, info |
| outline | 6 | Step numbers, paused |
| destructive | **0** | Defined but never used |

---

## 6. Form Elements

| Element | Instances | Key Contexts |
|---------|-----------|-------------|
| **Input** | 48 | Task creation, config, search, login, agent/squad forms |
| **Textarea** | 15 | Thread input, chat, prompts, squad specs |
| **Select** | 13 | Agent/model selection, settings |
| **Checkbox** | 9 | Skills, board agents, blockers |
| **Switch** | 3 | Agent toggle, settings booleans |
| **Total** | **88** | |

**Issue:** 6+ places use raw HTML `<select>` instead of shadcn Select. 3+ places use raw `<input>` instead of shadcn Input.

---

## 7. Layout Architecture

### Main Layout Structure

```
BoardProvider
  SidebarProvider
    AgentSidebar (left, 240px desktop / 288px mobile / 64px collapsed)
    SidebarInset
      div.flex.h-screen.flex-col.overflow-hidden
        header (h-[60px], border-b)
        TaskInput (border-b, px-4 py-3)
        KanbanBoard | TerminalBoard (flex-1, px-4 py-4)
    ActivityFeedPanel (right, 280px activity / 420px chats)
    TaskDetailSheet (overlay, 50vw)
    Settings/Tags Sheets (overlays)
```

### Key Dimensions

| Element | Value |
|---------|-------|
| Header height | `60px` |
| Sidebar width (desktop) | `240px` (15rem) |
| Sidebar width (mobile) | `288px` (18rem) |
| Sidebar collapsed | `64px` (4rem) |
| Activity panel (activity) | `280px` |
| Activity panel (chats) | `420px` |
| Kanban columns | `5-column grid` (md+) |
| Kanban column mobile | `85vw` snap |

### Responsive Breakpoints

| Breakpoint | Key Changes |
|------------|-------------|
| **sm** (640px) | Sheet widths, dialog sizing, text alignment |
| **md** (768px) | **Primary breakpoint** — sidebar toggle, kanban grid, activity panel inline |
| **lg** (1024px) | Thread max-width |
| **xl** (1280px) | Sidebar auto-open, wider content areas |

---

## 8. Sheets & Modals

### Sheets (all right-side, except mobile sidebar = left)

| Sheet | Width | Purpose |
|-------|-------|---------|
| Task Detail | `90vw` / `sm:50vw` | Full task view with tabs |
| Squad Detail | `96vw` / `sm:max-w-6xl` | Squad workflow editor |
| Settings | `sm:600px` | Global settings |
| Done Tasks | `480px` | Completed tasks list |
| Trash Bin | `480px` | Deleted tasks list |
| Agent Config | `480px` | Agent configuration |
| Board Settings | `400px` | Board configuration |
| Tags | `400px` | Tag management |

**Pattern:** All sheets use `p-0` on SheetContent and `px-6 py-4` internally.

### Dialogs

| Dialog | Width | Purpose |
|--------|-------|---------|
| Document Viewer | `max-w-4xl h-[80vh]` | File preview |
| Cron Jobs | `max-w-4xl max-h-[80vh]` | Cron management |
| Agent/Squad Wizard | `max-w-4xl h-[600px]` | AI-assisted creation |
| Agent Text Viewer | `max-w-3xl` | Text preview |
| Prompt Editor | `max-w-3xl` | Prompt editing |
| Board Create | `sm:max-w-md` | Board form |
| Squad Mission | `sm:max-w-[480px]` | Mission launch |
| Confirmations | `max-w-lg` (default) | AlertDialogs |

---

## 9. Spacing Patterns

### Most Used Values

| Category | Top Values |
|----------|-----------|
| **Padding** | `px-2` (131), `px-3` (97), `py-2` (97), `py-1` (58), `px-6` (43) |
| **Gap** | `gap-2` (132), `gap-1` (115), `gap-1.5` (37), `gap-3` (32) |
| **Space** | `space-y-1` (60), `space-y-2` (37), `space-y-4` (16) |
| **Margin** | `mt-1` (52), `mr-1` (43), `mt-2` (31), `mb-2` (25) |

**The project favors tight spacing:** `gap-1`/`gap-2`, `space-y-1`/`space-y-2`, `px-2`/`px-3`.

---

## 10. Animations & Transitions

### Tailwind Animations

| Animation | Occurrences | Usage |
|-----------|-------------|-------|
| `animate-spin` | 22 (9 files) | Loader2 icon spinners |
| `animate-pulse` | 9 (7 files) | Skeletons, live status dots |
| `animate-bounce` | 3 (1 file) | Typing indicator dots |
| `animate-pulse-once` | 1 | HITL badge count pulse (custom) |

### Motion Library (`motion/react`)

Used in **7 files**:

| Pattern | Duration | Files |
|---------|----------|-------|
| **Layout animation** (card reorder) | 300ms | TaskCard, StepCard |
| **Height reveal** (confirm bars) | 150ms | InlineRejection, KanbanColumn, StepCard, TaskCard |
| **Fade in** (list items) | 200ms | ActivityFeed, TaskDetailThreadTab |
| **LayoutGroup** (coordinated) | — | KanbanBoard |

**Accessibility:** `useReducedMotion` respected in 4 files.

**Bug:** Exit animations defined but non-functional — `AnimatePresence` is never used.

### CSS Transitions

| Class | Occurrences | Usage |
|-------|-------------|-------|
| `transition-colors` | 69 | Hover/focus color changes |
| `transition-opacity` | 16 | Show/hide on hover |
| `transition-transform` | 8 | Chevron rotation |
| `transition-all` | 6 | Panel width changes |
| `transition-shadow` | 3 | Card hover |

### Duration Values

| Duration | Context |
|----------|---------|
| `200ms` | Most transitions (default) |
| `300ms` | File fade-in, motion layout |
| `500ms` | Sheet open |
| `150ms` | Height reveal animations |

### tailwindcss-animate Plugin

Used in 9 shadcn/ui components for enter/exit animations:
`animate-in`, `animate-out`, `fade-in-0`, `fade-out-0`, `zoom-in-95`, `zoom-out-95`, `slide-in-from-*`, `slide-out-to-*`.

---

## 11. Status Color System

### Task Status Colors (`lib/constants.ts`)

| Status | Border Color | Bg | Text |
|--------|-------------|-----|------|
| `inbox` | `violet-500` | violet-100/950 | violet-700/300 |
| `review` | `amber-500` | amber-100/950 | amber-700/300 |
| `in_progress` | `blue-500` | blue-100/950 | blue-700/300 |
| `retrying` | `amber-600` | amber-100/950 | amber-700/300 |
| `done` | `green-500` | green-100/950 | green-700/300 |
| `crashed` | `red-500` | red-100/950 | red-700/300 |
| `ready` | `teal-500` | teal-100/950 | teal-700/300 |
| `failed` | `rose-500` | rose-100/950 | rose-700/300 |
| `assigned` | `cyan-500` | cyan-100/950 | cyan-700/300 |
| `deleted` | `gray-400` | gray-100/900 | gray-500/400 |

### Step Status Colors

| Status | Border Color |
|--------|-------------|
| `planned` | slate-400 |
| `assigned` | cyan-500 |
| `running` | blue-500 |
| `review` | amber-500 |
| `completed` | green-500 |
| `crashed` | red-500 |
| `blocked` | amber-500 |
| `waiting_human` | amber-500 |
| `deleted` | gray-400 |

### Tag Colors (8-color palette)

blue, green, red, amber, violet, pink, orange, teal — each with `bg`, `text`, `dot` variants.

### Agent Status Colors (inline, not centralized)

| Status | Style |
|--------|-------|
| active | `bg-blue-500` + blue glow shadow |
| crashed | `bg-red-500` + red glow shadow |
| idle | No special styling |

**12 Tailwind color families** in use: teal, rose, violet, cyan, blue, amber, green, red, gray, slate, orange, pink, emerald.

---

## 12. Custom Feature Components

### By Feature Module

| Module | Components | Largest File |
|--------|-----------|-------------|
| **agents** | 17 components | AgentConfigSheet (1089 lines) |
| **tasks** | 11 components | ExecutionPlanTab (968 lines) |
| **interactive** | 5 components | InteractiveTerminalPanel (482 lines) |
| **boards** | 3 components | BoardSettingsSheet (306 lines) |
| **thread** | 2 components | ThreadInput (301 lines) |
| **settings** | 3 components | SettingsPanel (402 lines) |
| **search** | 1 component | SearchBar (253 lines) |
| **activity** | 2 components | ActivityFeedPanel (91 lines) |
| **terminal** | 1 component | TerminalBoard (56 lines) |

### Shared Components (non-ui)

27 components in `dashboard/components/`, plus 4 viewer components.

### Components >400 Lines (decomposition candidates)

| Component | Lines |
|-----------|-------|
| AgentConfigSheet | 1089 |
| ExecutionPlanTab | 968 |
| TaskDetailSheet | 788 |
| TaskDetailHeader | 661 |
| TaskInput | 630 |
| SquadWorkflowCanvas | 533 |
| SquadDetailSheet | 528 |
| AgentSidebar | 526 |
| CronJobsModal | 492 |
| FlowStepNode | 478 |
| TaskDetailConfigTab | 445 |
| SettingsPanel | 402 |

### Reusable Patterns (not yet extracted)

| Pattern | Used In | Suggested Component |
|---------|---------|-------------------|
| Tag chips (colored dot + label pill) | TaskCard, TaskDetailHeader, TaskDetailConfigTab, TaskInput, SearchBar, TagsPanel | `<TagChip>` |
| Status card with left border accent | TaskCard, StepCard | `<StatusCard>` |
| Inline delete confirm (animated) | TaskCard, StepCard, KanbanColumn | `<InlineConfirm>` |
| Dark terminal header (status + agent + pills) | InteractiveTerminalPanel, TerminalPanel, ProviderLiveChatPanel, AgentActivityFeed | `<TerminalHeader>` |
| Done/Trash task list sheet | DoneTasksSheet, TrashBinSheet | `<TaskListSheet>` |

---

## 13. Issues & Inconsistencies

### Design System Violations

1. **Missing Button variants**: ~12 instances of hardcoded green buttons (approve/resume/start). Need `success` variant.
2. **Unused variants**: `Button variant="link"` and `Badge variant="destructive"` defined but never used.
3. **Raw HTML elements bypassing shadcn**: 6+ native `<select>`, 3+ native `<input>`, 0 uses of `role="button"`.
4. **Hardcoded colors in components**: Terminal themes duplicated in 2 files, Telegram brand color inline.

### Dark Mode Issues

5. **ThreadMessage** uses light-mode-only colors (`bg-blue-50`, `bg-green-50`, etc.) without `dark:` variants.
6. **TaskDetailHeader** error banners use `bg-red-50 border-red-200 text-red-800` without dark variants.
7. **CronJobsModal** status badges use hardcoded light colors.

### Accessibility

8. **6+ icon-only SVGs with onClick** but no button wrapper (Trash2, Star in TaskCard, StepCard, CompactFavoriteCard).
9. **5+ clickable divs** acting as primary targets without keyboard support.
10. **`focus-visible:` sparse** in app code (7 instances outside UI primitives).
11. **`active:` pseudo-class** barely used (4 instances) — no press feedback.
12. **Zero uses of `role="button"`** on non-button clickable elements.

### Code Quality

13. **`formatSize` utility** duplicated identically in 3 files.
14. **SquadWorkflowEditor vs SquadWorkflowCanvas** — step editor form duplicated (~200 lines).
15. **DoneTasksSheet vs TrashBinSheet** — ~80% structural duplication.
16. **Tag chip rendering** — same TAG_COLORS logic duplicated in 6 files.
17. **12 components exceed 400 lines** — decomposition recommended.

### Animation Bugs

18. **Exit animations broken**: `exit` props defined on `motion.div` but `AnimatePresence` never wraps conditional renders.
19. **No spring/physics animations**: All motion uses linear duration-based timing.

### Localization

20. **Mixed language strings**: Portuguese "Publicando..."/"Publicar"/"Remoto" found in SquadDetailSheet and AgentSidebar.

### Color Sprawl

21. **12 Tailwind color families** in status system (teal, rose, violet, cyan, blue, amber, green, red, gray, slate, orange, pink, emerald) — all from default palette, not from theme CSS variables.
22. **Agent status colors** defined inline in AgentSidebarItem instead of centralized constants.
23. **Ad-hoc severity colors** in FeedItem, CronJobsModal, DashboardLayout, TaskDetailHeader, ProviderLiveEventRow — not using centralized constants.

---

## 14. Visual Catalog (Screenshots)

All screenshots are in `docs/design-audit/screenshots/`. Each image documents the current visual state of a component for design book reference.

### Dashboard Views

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `01-dashboard-full-light.png` | Full dashboard — light mode | Sidebar (240px, agent avatars with colored circles + initials, squad section, collapsible groups), Header (60px, "Mission Control" title, board selector dropdown, search bar, gateway status badge, icon buttons), Task input (title + description inputs, Create button, AI/Manual toggle, agent selector), Kanban board (5 columns: Inbox/Assigned/In Progress/Review/Done, colored dot indicators, collapsible tag groups with counts) |
| `01-dashboard-full-dark.png` | Full dashboard — dark mode | Same layout. Dark backgrounds (#0c0a09), light text (#fafaf9), dark card surfaces for kanban columns, sidebar bg (#18181b). Gateway badge inverts to dark border. Agent avatar colors remain the same. |
| `05-kanban-inbox-cards-light.png` | Kanban with task cards expanded | Task cards: white bg, violet left border (3px, `border-l-violet-500` for inbox), title (text-sm font-medium, 2-line clamp), tag chips (rounded-full, gray bg "open-control", violet bg "inbox"), star icon (unfilled), agent icon (unassigned), chevron expand, trash icon bottom-right |

### Header & Navigation

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `02-header-bar.png` | Isolated header bar | "Mission Control" (text-xl font-bold), "Default" board selector (outline button + chevron), filter icon, Search input (border, rounded-md, placeholder "Search tasks..."), Gateway status badge (green border, green text "Gateway sleeping · sync in X:XX"), "Wake now" button, Clock/Tags/Settings/Activity icons (ghost buttons, h-9 w-9) |
| `23-board-selector-light.png` | Board dropdown open | Dropdown menu showing board list, "New Board" option with plus icon. DropdownMenu styling: rounded-md border, bg-popover, shadow-md |

### Sidebar

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `03-sidebar-agents-light.png` | Full sidebar | Bot icon + "Agents" title + toolbar (trash, panel icons). "Create" button (plus icon, sidebar menu button). Search input. **Squads section**: purple/violet avatars with 2-letter initials (IC, PP, DC), name + description (text-sm, text-xs muted). **Registered section**: collapsible with chevron, agents with colored circle avatars (CR=red, DS=blue, FP=purple, IC=cyan, MC=yellow, OS=green, SR=blue, YS=brown), idle status dots (gray). |

### Task Input

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `04-task-input-light.png` | Task creation bar | Two-row layout: Title input (placeholder "Task title...", full width), Description input (placeholder "Description..."). Right side: "Create" button (bg-primary, text-primary-foreground, rounded-md), paperclip attach button (icon variant), AI toggle button (icon + "AI" text), Agent selector combobox ("Auto (Lead Agent)" with chevron) |

### Task Detail Sheet

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `06-task-detail-thread-tab-light.png` | Empty thread tab (inbox task) | Sheet (right side, ~50vw): Title (text-lg font-semibold), status badge "inbox" (violet bg, rounded-md), tag chip "open-control" (secondary badge), description placeholder, trash icon. **Tabs**: Thread (active, bg-background shadow)/Execution Plan/Config/Files. Empty state: "No messages yet. Agent activity will appear here." **Thread input**: "Reply" label, agent selector combobox, textarea with placeholder, send button (disabled, icon), attach button |
| `10-thread-tab-populated-light.png` | Thread with messages (Ifood task) | Sheet header: "done" badge (green bg), "Squad: Instagram Content Squad" + "Workflow: content-creation" outline badges. **Messages**: Step filter dropdown at top. Agent messages with colored avatar circles, name, timestamp. Message bubbles with markdown content (rendered paragraphs, bullet lists). Different bg colors by message type. Artifact links inline. |
| `11-thread-tab-populated-dark.png` | Thread messages — dark mode | Same content. Dark bg (#0c0a09), message bubbles with dark variants, lighter text. Avatar colors unchanged. Tab bar bg-muted dark variant. |
| `12-execution-plan-tab-light.png` | Execution plan with canvas | "7/7 steps completed" counter. View mode toggles: Both/Canvas/Lead Agent Conversation (pill-shaped ToggleGroup). **ReactFlow canvas**: Start node (rounded-full, green play icon) → FlowStepNodes (rounded-lg border bg-background, 220px wide, step title + agent name, green checkmark "Done" badge) → branching parallel paths → End node. Edges with bezier curves. Zoom controls (+-) bottom-left. |
| `12-execution-plan-tab-dark.png` | Execution plan — dark mode | Dark canvas bg, nodes with dark bg-background, light text. Edges dark. Same layout. |
| `07-task-detail-plan-tab-light.png` | Empty execution plan | "No steps yet" text, "Add Step" button (plus icon, outline style). View mode toggles visible but empty. |
| `13-config-tab-light.png` | Config tab populated | **Merge section**: "MERGE WITH ANOTHER TASK" heading (text-xs uppercase tracking-wider), search input, merge candidate cards (title + description preview). "Generate Plan Then Send To Review" button (bg-green-600, custom color override). "Create Manual Review Task" button (outline). **Trust Level**: "autonomous" (text-sm font-bold). **Tags**: tag chip "open-control" with X remove, "+" add button. |
| `08-task-detail-config-tab-light.png` | Config tab (inbox task) | Same layout but for inbox task. Shows merge candidates list and tag management. |
| `14-files-tab-light.png` | Files tab with 7 files | **Output section**: File rows with icons (FileText for .md, Image for .svg), file name, source badge "output" (secondary), file size (text-xs muted). Rows separated by borders. |
| `14-files-tab-dark.png` | Files tab — dark mode | Dark bg, file rows with dark borders, same icon and layout structure. |

### Settings & Configuration

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `20-settings-panel-light.png` | Settings sheet | Sheet (right, 600px): "Settings" title, "Configure global system defaults" subtitle. **Theme**: 3 icons (sun/auto/monitor) in a toggle group. **Task Timeout**: labeled number input "30". **Inter-Agent Review Timeout**: "10". **Global Orientation Prompt**: monospace textarea with "Edit" pencil link. **Default LLM Model**: Select dropdown "Medium". **Auto Title**: Switch toggle (off). |
| `20-settings-panel-dark.png` | Settings — dark mode | Dark bg, inputs with dark borders, select with dark bg. Theme icons visible. Same layout. |
| `21-tags-panel-light.png` | Tags management sheet | Sheet (right, 400px): Tag list with colored dots (blue, green) + name + X remove button. **Attributes section**: attribute chips per tag. **Color picker**: 8 circle buttons (blue/green/red/amber/violet/pink/orange/teal). Create form with input + "Add Tag" button. |
| `22-cron-jobs-modal-light.png` | Cron jobs modal | Dialog (max-w-4xl): Table layout with columns: Name, Schedule, Channel, Status. Cron entry with name (link, hover:underline), schedule string, channel badge, status badge (green "ok" or red "error"). Inline Telegram icon (#229ED9 brand color). Delete/edit actions. |

### Agent & Squad Management

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `30-agent-config-light.png` | Agent config sheet | Sheet (right, 480px): Agent avatar circle (yellow "MC") with "idle" status dot. "Active" Switch toggle (on). **Form fields**: Name (input "marketing-copy"), Display Name ("Marketing Copy"), Role (input), Prompt (monospace textarea with "Edit" link), Soul (heading + textarea), Model (Select dropdown "Claude Code..."). Cancel/Save buttons at bottom. |
| `30-agent-config-dark.png` | Agent config — dark mode | Dark bg, form inputs with dark borders, monospace text on dark bg. Same layout. |
| `31-squad-detail-light.png` | Squad detail sheet | Sheet (right, 96vw): "Instagram Content Squad" title + "published" badge (dark). "Edit Squad"/"Run Mission" buttons. **Outcome** section: text description. **Agents (5)**: Grid of agent cards (rounded-xl border, Bot icon + name + role text, collapsible "1 skill" link). **Workflows section**: "content-creation" label. Tabbed: Workflow/Steps/Criteria. **ReactFlow canvas**: START node → sequential/parallel FlowStepNodes → END node. Step nodes show agent assignment. |
| `31-squad-detail-dark.png` | Squad detail — dark mode | Dark bg, agent cards with dark borders, dark canvas. Same layout. |

### Activity & Lists

| Screenshot | Description | Key Elements Visible |
|-----------|-------------|---------------------|
| `40-activity-feed-light.png` | Activity feed panel open | Right panel (280px): "ACTIVITY" header with collapse icon. **Event list**: Each event has timestamp (text-xs muted), event type with colored label (green for registration, emerald for transitions, amber for steps), description text. Events: agent registrations, task status changes, step transitions. Scrollable with many entries. |
| `41-done-tasks-sheet-light.png` | Done tasks sheet | Sheet (right, 480px): "Done Tasks" title with CheckCircle2 icon + count badge "30" (secondary). Task rows: title (text-sm), "On board" or "Cleared" badge (secondary), relative time, Restore button (RotateCcw icon) + Delete button (Trash2 icon). Scrollable list. |
| `50-task-cards-inbox-light.png` | Inbox cards close-up | Multiple task cards in Inbox column. Cards show: title (2-line clamp), tag chips, status badge, star/agent/expand icons. Some cards have description paragraphs visible. Cards have violet left border for inbox status. |
| `50-task-cards-done-light.png` | Done cards close-up | Done column cards with: green left border, title, step progress indicator (img + "X/X steps" text), "done" green badge, file count with paperclip icon, agent name. Cards more compact than inbox cards. |

### Component Characteristics Summary

| Component | Light Mode BG | Dark Mode BG | Border | Border Radius | Padding | Shadow |
|-----------|--------------|-------------|--------|--------------|---------|--------|
| Dashboard | `#ffffff` | `#0c0a09` | — | — | — | — |
| Sidebar | `#fafafa` | `#18181b` | right border | — | p-2 | — |
| Header | `#ffffff` | `#0c0a09` | bottom border | — | px-4 h-[60px] | — |
| Task Card | `#ffffff` | `#0c0a09` | border + left-3px accent | rounded-xl | p-3 | shadow (hover: shadow-md) |
| Sheet | `#ffffff` | `#0c0a09` | left border | — | p-0 (custom internal) | shadow-lg |
| Dialog | `#ffffff` | `#0c0a09` | border | rounded-lg | p-6 | shadow-lg |
| Input | transparent | transparent | border-input | rounded-md | px-3 py-1 h-9 | shadow-sm |
| Button (default) | `#1c1917` | `#fafaf9` | — | rounded-md | px-4 py-2 h-9 | shadow |
| Button (ghost) | transparent | transparent | — | rounded-md | px-4 py-2 h-9 | — |
| Badge (status) | status-color-100 | status-color-950 | transparent | rounded-md | px-2.5 py-0.5 | — |
| Tag Chip | tag-color-100 | tag-color-950 | — | rounded-full | px-2 py-0.5 | — |
| Avatar Circle | hash-based color | hash-based color | — | rounded-full | — | — |
| Tabs | bg-muted | bg-muted | — | rounded-lg | p-1 (list) | — |
| Tab (active) | bg-background | bg-background | — | rounded-md | px-3 py-1 | shadow |
| FlowStepNode | bg-background | bg-background | border | rounded-lg | px-3 py-2 | shadow-sm |
