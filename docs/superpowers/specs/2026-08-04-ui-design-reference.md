# UI Design Reference — match the Base44 prototype

Source: https://tomorrow-agent-hub.base44.app (captured 2026-08-04, user instruction:
"Make the UI same as this"). The prototype is a simplified single-municipality version;
we apply its visual language to every screen in the scope appendix.

## Design tokens (shadcn/ui-style HSL, copied from the live prototype)

```css
--background: 40 20% 97%;        /* warm off-white #f9f8f6 */
--foreground: 240 28% 14%;       /* dark ink navy */
--card: 0 0% 100%;
--card-foreground: 240 28% 14%;
--primary: 180 41% 30%;          /* deep teal */
--primary-foreground: 0 0% 100%;
--secondary: 180 38% 93%;        /* pale teal */
--accent: 180 38% 93%;
--accent-foreground: 180 41% 24%;
--muted: 40 15% 94%;
--muted-foreground: 240 8% 46%;
--border: 0 0% 88%;
--ring: 180 41% 30%;
--destructive: 0 72% 51%;
--radius: 0.5rem;
--sidebar-background: 0 0% 100%;
--sidebar-foreground: 240 12% 30%;
--sidebar-primary: 180 41% 30%;
--sidebar-primary-foreground: 0 0% 100%;
--sidebar-accent: 180 38% 93%;
--sidebar-accent-foreground: 180 41% 24%;
--sidebar-border: 0 0% 90%;
--chart-1: 180 41% 30%;  /* teal */
--chart-2: 173 58% 39%;
--chart-3: 27 87% 60%;   /* orange */
--chart-4: 240 50% 55%;  /* indigo */
--chart-5: 340 60% 55%;  /* pink */
```

**Font:** Heebo (Google Fonts) for both Hebrew and English — `Heebo, ui-sans-serif, system-ui,
sans-serif`, loaded via `next/font`.

## Layout & components (observed)

- **App shell:** sidebar `w-64` on the logical start side (right in RTL — `border-l` there),
  white background, sticky full-height, hidden under `md` (hamburger drawer). Content area has
  the warm background with a subtle decorative radial gradient wash (peach + teal tints).
- **Sidebar structure:** top = logo chip (teal rounded-xl square, white sparkles icon) +
  app name (bold) + program subtitle (muted, small). Middle = nav items, right-aligned text
  with lucide icon at the logical start; active item is a **full-width teal pill
  (rounded-full) with white text**; inactive items muted ink. Bottom = user display name
  (semibold) + role (muted small) + sign-out link with icon.
- **Page headers:** large bold title (~text-3xl/4xl) in ink, one-line muted subtitle under it.
  Primary action button top-left (RTL end): teal, rounded-lg, white text, lucide icon.
- **Cards:** white, `rounded-xl`, subtle shadow (shadow-sm/md on hover), generous padding.
  Board item card: pastel category chip (tinted bg + darker text of same hue — orange, purple,
  etc.), bold title, 2-3 line muted description, file/link chip with icon, footer row with
  author · date (muted, start side) and like/comment counts with icons (end side); delete icon
  top corner for owners/admins.
- **List rows (KB documents):** white rounded-xl row, pale-teal rounded-lg file-icon tile at
  the start, filename semibold + muted meta line (type · date), delete icon at the end.
- **Info banner:** pale teal (`--accent`) rounded-lg strip with icon + small text.
- **Empty states:** centered pale-teal rounded-2xl icon tile, bold title, muted caption,
  teal CTA button underneath.
- **Chat:** header row with teal sparkle avatar + bold title + muted "based on the shared
  knowledge base" subtitle, bordered bottom; assistant messages = white rounded-xl cards with
  a small teal sparkle avatar beside; user messages = teal-tinted bubble; input bar fixed at
  bottom: rounded-lg bordered input + square teal send button (paper-plane icon).
- **Forms/inputs:** white bg, `rounded-lg`, 1px `--border`, focus ring in `--ring`.
- **Icons:** lucide-react throughout.
- **Charts (dashboards):** use `--chart-*` palette.

## Application notes for our build

- Implement tokens in `web/app/globals.css` under `@theme`/CSS vars; use logical properties
  (`ms-`, `me-`, `start-`, `end-`) everywhere so RTL mirrors for free.
- The prototype is Hebrew-only; our build renders the same design in `he` (RTL) and `en` (LTR).
- Prototype nav labels for reference: סוכן מחר (Assistant), בסיס מחר (Knowledge Base),
  לוח שיתוף (Shared Board), ניהול משתמשים (Users), מדדי שימוש (Usage). Keep this naming
  flavor in `he.json` copy.
