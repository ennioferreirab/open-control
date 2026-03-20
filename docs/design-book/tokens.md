# Design Tokens

All tokens defined as CSS custom properties in HSL format for shadcn/ui compatibility. Every token has both dark (`:root` default, dark-first) and light (`.light`) values.

---

## Color Tokens

### Core Surfaces

```css
:root {
  /* Dark mode (default) */
  --background: 0 0% 6.7%;           /* #111111 */
  --foreground: 0 0% 93.3%;          /* #eeeeee */

  --card: 0 0% 9.8%;                 /* #191919 */
  --card-foreground: 0 0% 93.3%;     /* #eeeeee */

  --popover: 0 0% 9.8%;              /* #191919 */
  --popover-foreground: 0 0% 93.3%;  /* #eeeeee */

  --muted: 0 0% 13.3%;              /* #222222 */
  --muted-foreground: 0 0% 53.3%;   /* #888888 */

  --accent: 0 0% 13.3%;             /* #222222 */
  --accent-foreground: 0 0% 93.3%;  /* #eeeeee */

  --secondary: 0 0% 13.3%;          /* #222222 */
  --secondary-foreground: 0 0% 93.3%; /* #eeeeee */

  --border: 0 0% 16.5%;             /* #2a2a2a */
  --input: 0 0% 16.5%;              /* #2a2a2a */
  --ring: 211 73% 51%;              /* #2383e2 */
}

.light {
  --background: 0 0% 100%;          /* #ffffff */
  --foreground: 0 0% 10%;           /* #1a1a1a */

  --card: 0 0% 97.6%;               /* #f9f9f9 */
  --card-foreground: 0 0% 10%;      /* #1a1a1a */

  --popover: 0 0% 100%;             /* #ffffff */
  --popover-foreground: 0 0% 10%;   /* #1a1a1a */

  --muted: 0 0% 96.1%;              /* #f5f5f5 */
  --muted-foreground: 0 0% 42%;     /* #6b6b6b */

  --accent: 0 0% 96.1%;             /* #f5f5f5 */
  --accent-foreground: 0 0% 10%;    /* #1a1a1a */

  --secondary: 0 0% 96.1%;          /* #f5f5f5 */
  --secondary-foreground: 0 0% 10%; /* #1a1a1a */

  --border: 0 0% 89.8%;             /* #e5e5e5 */
  --input: 0 0% 89.8%;              /* #e5e5e5 */
  --ring: 211 73% 51%;              /* #2383e2 */
}
```

### Interactive Colors

```css
:root {
  /* Primary — Notion blue, used for CTAs and primary actions */
  --primary: 211 73% 51%;              /* #2383e2 */
  --primary-foreground: 0 0% 100%;     /* #ffffff */

  /* Destructive — danger, delete, deny */
  --destructive: 0 72% 53%;            /* #da3633 */
  --destructive-foreground: 0 0% 100%; /* #ffffff */

  /* Success — approve, complete, confirm (NEW) */
  --success: 137 52% 44%;              /* #2ea043 */
  --success-foreground: 0 0% 100%;     /* #ffffff */

  /* Warning — review, caution, attention (NEW) */
  --warning: 39 72% 49%;               /* #d29922 */
  --warning-foreground: 0 0% 100%;     /* #ffffff */

  /* Info — informational highlights */
  --info: 211 73% 51%;                 /* #2383e2 (same as primary) */
  --info-foreground: 0 0% 100%;        /* #ffffff */
}

.light {
  --primary: 211 91% 41%;              /* #0b6bcb */
  --primary-foreground: 0 0% 100%;     /* #ffffff */

  --destructive: 1 76% 49%;            /* #cf222e */
  --destructive-foreground: 0 0% 100%; /* #ffffff */

  --success: 140 61% 35%;              /* #1a7f37 */
  --success-foreground: 0 0% 100%;     /* #ffffff */

  --warning: 36 100% 30%;              /* #9a6700 */
  --warning-foreground: 0 0% 100%;     /* #ffffff */

  --info: 211 91% 41%;                 /* #0b6bcb */
  --info-foreground: 0 0% 100%;        /* #ffffff */
}
```

### Status Colors

Centralized status tokens replace the scattered Tailwind color classes currently used in `lib/constants.ts` and inline across components.

```css
:root {
  /* Task/Step statuses */
  --status-inbox: 262 83% 68%;              /* violet — #a78bfa */
  --status-inbox-foreground: 262 83% 85%;   /* light violet */
  --status-inbox-muted: 262 83% 15%;        /* bg tint */

  --status-assigned: 187 72% 55%;           /* cyan — #22d3ee */
  --status-assigned-foreground: 187 72% 85%;
  --status-assigned-muted: 187 72% 12%;

  --status-progress: 211 73% 51%;           /* blue — #2383e2 */
  --status-progress-foreground: 211 73% 85%;
  --status-progress-muted: 211 73% 12%;

  --status-review: 39 72% 49%;              /* amber — #d29922 */
  --status-review-foreground: 39 72% 85%;
  --status-review-muted: 39 72% 12%;

  --status-done: 137 52% 44%;               /* green — #2ea043 */
  --status-done-foreground: 137 52% 85%;
  --status-done-muted: 137 52% 12%;

  --status-error: 0 72% 53%;                /* red — #da3633 */
  --status-error-foreground: 0 72% 85%;
  --status-error-muted: 0 72% 12%;

  --status-deleted: 0 0% 40%;               /* gray — #666666 */
  --status-deleted-foreground: 0 0% 60%;
  --status-deleted-muted: 0 0% 12%;
}

.light {
  --status-inbox: 262 83% 58%;
  --status-inbox-foreground: 262 83% 30%;
  --status-inbox-muted: 262 83% 95%;

  --status-assigned: 187 72% 42%;
  --status-assigned-foreground: 187 72% 25%;
  --status-assigned-muted: 187 72% 95%;

  --status-progress: 211 73% 51%;
  --status-progress-foreground: 211 73% 30%;
  --status-progress-muted: 211 73% 95%;

  --status-review: 39 72% 40%;
  --status-review-foreground: 39 72% 25%;
  --status-review-muted: 39 72% 95%;

  --status-done: 137 52% 37%;
  --status-done-foreground: 137 52% 22%;
  --status-done-muted: 137 52% 95%;

  --status-error: 0 72% 45%;
  --status-error-foreground: 0 72% 25%;
  --status-error-muted: 0 72% 95%;

  --status-deleted: 0 0% 62%;
  --status-deleted-foreground: 0 0% 40%;
  --status-deleted-muted: 0 0% 95%;
}
```

### Sidebar

```css
:root {
  --sidebar: 0 0% 7.8%;               /* #141414 */
  --sidebar-foreground: 0 0% 80%;     /* #cccccc */
  --sidebar-primary: 211 73% 51%;     /* #2383e2 */
  --sidebar-primary-foreground: 0 0% 100%;
  --sidebar-accent: 0 0% 13.3%;       /* #222222 */
  --sidebar-accent-foreground: 0 0% 93.3%;
  --sidebar-border: 0 0% 14%;         /* #242424 */
  --sidebar-ring: 211 73% 51%;        /* #2383e2 */
}

.light {
  --sidebar: 0 0% 98%;                /* #fafafa */
  --sidebar-foreground: 0 0% 25%;     /* #404040 */
  --sidebar-primary: 211 91% 41%;     /* #0b6bcb */
  --sidebar-primary-foreground: 0 0% 100%;
  --sidebar-accent: 0 0% 96%;         /* #f5f5f5 */
  --sidebar-accent-foreground: 0 0% 10%;
  --sidebar-border: 0 0% 90%;         /* #e6e6e6 */
  --sidebar-ring: 211 91% 41%;
}
```

### Tag Colors (8-color palette)

```css
:root {
  /* Each tag color has: main, foreground, muted (bg tint) */
  --tag-blue: 211 73% 55%;
  --tag-blue-foreground: 211 73% 85%;
  --tag-blue-muted: 211 73% 12%;

  --tag-green: 142 52% 50%;
  --tag-green-foreground: 142 52% 85%;
  --tag-green-muted: 142 52% 12%;

  --tag-red: 0 72% 55%;
  --tag-red-foreground: 0 72% 85%;
  --tag-red-muted: 0 72% 12%;

  --tag-amber: 39 72% 55%;
  --tag-amber-foreground: 39 72% 85%;
  --tag-amber-muted: 39 72% 12%;

  --tag-violet: 262 83% 65%;
  --tag-violet-foreground: 262 83% 85%;
  --tag-violet-muted: 262 83% 12%;

  --tag-pink: 330 81% 60%;
  --tag-pink-foreground: 330 81% 85%;
  --tag-pink-muted: 330 81% 12%;

  --tag-orange: 24 90% 55%;
  --tag-orange-foreground: 24 90% 85%;
  --tag-orange-muted: 24 90% 12%;

  --tag-teal: 174 62% 47%;
  --tag-teal-foreground: 174 62% 85%;
  --tag-teal-muted: 174 62% 12%;
}
```

Light mode: swap foreground ↔ muted (darker text on lighter bg).

---

## Typography

### Font Family

```css
:root {
  --font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
  --font-mono: 'Geist Mono', 'JetBrains Mono', ui-monospace, monospace;
}
```

**Why Inter over Geist**: Inter has better optical sizing, tabular figures, and wider adoption in professional dashboards. Geist Mono stays for code — it's excellent.

### Scale

| Token | Size | Line Height | Letter Spacing | Weight | Use |
|-------|------|-------------|----------------|--------|-----|
| `--text-display` | 28px | 1.2 | -0.02em | 700 | Hero headings (rare) |
| `--text-title` | 22px | 1.3 | -0.015em | 600 | Page titles ("Open Control") |
| `--text-heading` | 16px | 1.4 | -0.01em | 600 | Section headers, column titles |
| `--text-body` | 15px | 1.5 | 0 | 400 | Default text, descriptions |
| `--text-small` | 13px | 1.5 | 0 | 400 | Secondary info, card metadata |
| `--text-micro` | 11px | 1.4 | 0.01em | 500 | Timestamps, labels, badges |

### Weight Usage

| Weight | Token | Use |
|--------|-------|-----|
| 400 | `font-normal` | Body text, descriptions |
| 500 | `font-medium` | Labels, metadata, active tabs |
| 600 | `font-semibold` | Headings, button text, card titles |
| 700 | `font-bold` | Display headings only |

---

## Spacing

4px base grid. All spacing values are multiples of 4.

| Token | Value | Tailwind | Common Use |
|-------|-------|----------|-----------|
| `--space-0` | 0 | `0` | — |
| `--space-0.5` | 2px | `0.5` | Tight inline gaps |
| `--space-1` | 4px | `1` | Icon-to-text gap |
| `--space-1.5` | 6px | `1.5` | Badge padding, tight stacks |
| `--space-2` | 8px | `2` | Between inline elements |
| `--space-3` | 12px | `3` | Default gap between elements |
| `--space-4` | 16px | `4` | Between sections, card padding |
| `--space-5` | 20px | `5` | Generous section spacing |
| `--space-6` | 24px | `6` | Sheet content padding (horizontal) |
| `--space-8` | 32px | `8` | Between major sections |
| `--space-10` | 40px | `10` | Page-level spacing |
| `--space-12` | 48px | `12` | Large gaps |
| `--space-16` | 64px | `16` | Maximum spacing |

---

## Border Radius

| Token | Value | Tailwind | Use |
|-------|-------|----------|-----|
| `--radius` | 8px | `rounded-lg` | **Default** — cards, buttons, popovers |
| `--radius-sm` | 4px | `rounded` | Badges, small pills, inline elements |
| `--radius-md` | 6px | `rounded-md` | Inputs, smaller cards |
| `--radius-lg` | 8px | `rounded-lg` | Cards, main containers |
| `--radius-xl` | 12px | `rounded-xl` | Dialogs, modal content |
| `--radius-2xl` | 16px | `rounded-2xl` | Large overlays, sheets |
| `--radius-full` | 9999px | `rounded-full` | Avatars, dots, circular buttons |

---

## Elevation & Shadows

Dark mode relies on borders and surface color differentiation rather than shadows. Light mode uses subtle shadows.

```css
:root {
  /* Dark mode — minimal shadows, rely on borders */
  --shadow-xs: 0 1px 2px 0 rgb(0 0 0 / 0.3);
  --shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.4);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.4);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.4);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.4);
}

.light {
  --shadow-xs: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
}
```

### Surface Hierarchy (Dark Mode)

| Layer | Color | Use |
|-------|-------|-----|
| Canvas | `#111111` (--background) | Page background |
| Surface | `#191919` (--card) | Cards, kanban columns, panels |
| Raised | `#222222` (--muted) | Popovers, dropdowns, elevated panels |
| Overlay | `#191919` + border | Sheets, dialogs (same as card but with border emphasis) |

Each layer is ~1-2% lighter than the one below, creating subtle depth without shadows.

---

## Motion Tokens

```css
:root {
  --duration-instant: 0ms;
  --duration-fast: 100ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --duration-slower: 500ms;

  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-in: cubic-bezier(0.4, 0, 1, 1);
  --easing-out: cubic-bezier(0, 0, 0.2, 1);
  --easing-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
```

See [motion.md](motion.md) for pattern library.
