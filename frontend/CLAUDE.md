# SpecForge frontend

Next.js 14 (App Router) + React 18 + TypeScript + Tailwind v3 + shadcn/ui (new-york) + Framer Motion + lucide-react. Run from repo root: `make dev-fe` (→ `localhost:3000`), `make typecheck`, `make lint`.

## Layout
- `app/` — App Router routes: `page.tsx` (Portfolio), `apps/` (App Registry), `projects/new` (wizard), `projects/[id]` (workspace), `projects/[id]/interview` (RU interview), `login`, `layout.tsx`, `template.tsx` (page transitions).
- `app/components/` — feature components; `app/components/ui/` — shadcn primitives (21); `app/components/portfolio/` — table/board/triage; `app/components/motion/` — shared motion wrappers.
- `lib/` — `api.ts`, `types.ts`, `hooks/` (SWR), `auth/`, `utils.ts` (`cn()`), `ui/` (badge/variant helpers).

## Design tokens — centralized
Single source of truth is **`app/globals.css` `:root`** (emerald accent `--accent`, `--bg-*`, `--text-*`, `--border-*`, `--status-*`, shadows, `--radius`). `tailwind.config.ts` maps those CSS vars to utility keys (`accent`, `success`, `warning`, `danger`, `info`, `ai`, `brain`, + shadcn keys `primary/secondary/muted/destructive/card/ring/...`). **Re-theme by editing `:root` only.** Light-only (no `.dark`). Components reference tokens two ways (both fine): `bg-[var(--accent)]` or semantic keys (`bg-accent`, `<Badge variant="success">`). Reuse `.card`/`.card-hover` from globals.

## Data fetching
- `lib/api.ts`: call backend via `api.*`. `apiFetch<T>` returns `json.data`; `apiFetchEnvelope<T>` returns `{data, meta}` (use for portfolio groups/totals + triage freshness).
- **`authedFetch`** is the auth-aware fetch (bearer + transparent 401 refresh-and-retry). Use it for ANY authenticated request that isn't plain JSON — **streaming (`/ask`) and file uploads** — or they'll surface a mid-session "unauthorized".
- Access token lives in `lib/auth/tokenStore` (in-memory); the refresh token is an httpOnly cookie. `types.ts` mirrors backend Pydantic schemas — keep them in sync.
- Hooks in `lib/hooks/` wrap SWR (`useProjects(filters)`, `useViews`, `useTriage`, `useUnderstanding`, `useApps`, …).

## Backend proxy (gotcha)
`next.config.mjs` rewrites `/api/*` → **`http://127.0.0.1:8000`** (IPv4, NOT `localhost`). On macOS `localhost` resolves to IPv6 `::1` first, which collides with other Docker services on `:8000`. Override with `NEXT_PUBLIC_API_BASE`.

## Conventions
- Mark interactive components `'use client'`. Toasts via **sonner** (`import { toast } from 'sonner'`). Animations honor `useReducedMotion()`.
- The app is responsive: `AppShell` is a static sidebar on `md+` and a slide-in drawer on mobile; card grids use container-relative `grid-cols-[repeat(auto-fill,minmax(...))]`.
- After UI changes, verify in a browser with the **dev-browser** skill (login `admin@specforge.test` / `SpecForge#Test2026!`).

## Don't
- Don't run `next build` while `make dev-fe` is running — they share `.next` and the build corrupts the dev server (blank pages). Restart `dev-fe` after any production build.
- Don't add a dark theme or PII surfaces (project-wide non-goals).
