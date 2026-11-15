# GUI Audit — ovnis-pr Dashboard

Audit date: 2026-08-23
Scope: `dashboard/` (React/Vite SPA) and the desktop launcher entry points at the
repo root. Every user-executable control in the shipped UI was located in
source, its handler read, and — wherever the environment allowed — exercised
live with Playwright against a running dev server backed by the bundled
sample data.

> **Status update (2026-10-25):** the Cases-tab controls inventoried below have
> since changed. The search box (`Search cases`, placeholder "Search by case,
> place, agency or year…") now also matches case id, year, decade and agency; the
> period/tier selects are labelled "Period"/"Tier"; the list is paginated; an
> empty result shows a "Reset search" action; and below 860px the table becomes
> cards inside a mobile shell. This audit is otherwise left as the 2026-08-23
> record. Current behaviour: `dashboard/README.md`.

## Overview

**What this app is.** OVNIS (`ovnis-pr`) is the historical UAP/anomalous-event
case-corpus producer for the PRII (Puerto Rico Integrated Intelligence)
federation. Per the repo README, its dashboard is explicitly a **diagnostic
tool for this producer only** (ADR 0001, Phase 2) — the supported end-user
product surface for the federation is the separate `thehub-pr` hub app, which
consumes this repo's data. That framing matters for how to read this audit:
the dashboard is intentionally small (one page, ~470 case records, no auth,
no write operations — every backend route is `GET`-only).

**Tech stack.**
- Frontend: React 19 + Vite 8, React Router 7 (`BrowserRouter`, or
  `HashRouter` when built for offline `file://` export), TanStack Query 5 for
  data fetching, shadcn/ui component set on Radix UI primitives, Tailwind CSS
  4.3.3 (upgraded from 3.4.19 — see the Cases-tab/Case-detail findings below,
  which trace back to this upgrade), MapLibre GL JS for the map, Recharts for
  the two bar charts, lucide-react for icons.
- Backend consumed by the dashboard: a thin read-only FastAPI service
  (`server/backend/main.py`) that reads the repo's own Git-native JSONL
  ledgers (`data/master/master_cases.jsonl`, `data/candidates/candidate_cases.jsonl`)
  and the latest release GeoJSON (`releases/<date>/ovnis_cases_master.geojson`).
  No external API keys or network services are required — this backend runs
  entirely off files already committed to the repo.
- Desktop wrapper: a shared `prii_desktop` package (fetched from the sibling
  `thehub-pr` repo as a pinned git+pip dependency) that runs the same FastAPI
  app same-origin with the built dashboard, in a native window.

**Entry points.**
- Dev: `cd dashboard && npm install && npm run dev` → Vite dev server
  (default `http://localhost:5173`), talking to the FastAPI backend at
  `VITE_API_BASE` (default `http://localhost:8000`, started separately with
  `uvicorn server.backend.main:app --port 8000`). The backend's CORS
  allow-list is hardcoded to `localhost:5173` / `127.0.0.1:5173`.
- Desktop launcher: double-click `PRII-OVNIS.command` (macOS Terminal
  launcher), `PRII-OVNIS.sh` (Linux), `PRII-OVNIS.bat` (Windows), or
  `PRII-OVNIS.app` (macOS Finder app bundle) — see the **Desktop Launcher**
  section below.
- Offline single-file export: `npm run build:export` (`VITE_OFFLINE=1`)
  produces a self-contained `dashboard/export-standalone/index.html` with the
  data snapshot baked in, openable directly via `file://`.

**Live-verification setup used for this audit.** `npm install` in
`dashboard/`, then `pip install fastapi "uvicorn[standard]"` and
`uvicorn server.backend.main:app --host 127.0.0.1 --port 8002` (port 8000 was
already occupied by a sibling audit session sharing this container; the
FastAPI backend's hardcoded CORS allow-list was temporarily patched to add
`127.0.0.1:5175`/`localhost:5175` for the duration of the test and reverted
before committing — `git status` confirms a clean tree). The Vite dev server
was started on port 5175 (`VITE_API_BASE=http://127.0.0.1:8002 npx vite
--port 5175 --strictPort`) and driven with Playwright (Node `playwright`
1.56.1, Chromium at `/opt/pw-browsers/chromium`, headless, `--no-sandbox`).
The bundled data (470 master cases, 1 placeholder candidate,
469 mapped/1 unmapped) rendered as real content — no external API keys
needed. Both servers were stopped and all temporary files/edits reverted at
the end of the session.

**A note on `dashboard/src/components`.** Of the 64 `.jsx`/`.tsx` files under
`dashboard/src`, 49 live in `components/ui/` — the shadcn/ui primitive
library (Radix wrappers: accordion, dialog, dropdown-menu, calendar, carousel,
etc.). Only a subset of these primitives is actually imported by the app's
own components; the rest ship in the library but are not currently wired into
any view. This audit catalogs every control the live app can actually reach,
and separately lists the unused primitives so the full 64-file surface is
accounted for (see **Unused shadcn/ui primitives**, at the end).

---

## View 1 — App Shell (`App.jsx`, `main.jsx`)

Router + global providers. One route (`/`) renders `Dashboard`; everything
else renders `PageNotFound`. No auth (explicitly stripped, per code comment).
A global `<Toaster />` is mounted but no code path in this repo currently
calls `toast(...)`, so it never appears in practice (see the CSS-positioning
finding under Case Detail — the same bug would mis-position it if it were
ever triggered).

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Router mode switch | logic (not a control) | — | `import.meta.env.VITE_OFFLINE === '1' ? HashRouter : BrowserRouter` — offline single-file exports use hash routing so `/` resolves under `file://`. | Static | Not user-facing. |
| `ErrorBoundary` "Try again" | button | Try again | `onClick={() => this.setState({ error: null })}` — clears the caught render error and re-renders children. Only appears if a component throws during render. | Static-only: requires forcing a render exception | Deliberately separate from `QueryState`: catches code that throws, not a failed fetch. Not exercised live (would require injecting a bad render). |
| `<Toaster />` (global) | toast/notification host | — | Renders any toast pushed via the shadcn `useToast()` hook. | Static-only: no code path calls `toast()` | Wired but dormant. See Case Detail finding — its `fixed top-0 …sm:bottom-0 sm:right-0` positioning shares the same missing-CSS defect as the Sheet drawer, so if ever triggered it would likely render mispositioned too. |

---

## View 2 — Dashboard header (`pages/Dashboard.jsx`, lines 30–42)

Static branding + a live backend-health readout. No clickable controls here,
but the health text is dynamic and was exercised live in both states.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Health status dot + label | status indicator (non-interactive) | e.g. `470 cases · 469 mapped · 1 unmapped` / `connecting…` / `backend unreachable` | Derived from `useHealth()` (`GET /health`, polls every 20s via `refetchInterval: 20_000`). Three states are distinguished on purpose (comment in source): loading vs. error vs. success, so an unreachable backend cannot be confused with "still connecting." | **Live** | Confirmed both states: backend up → `"470 cases · 469 mapped · 1 unmapped"`; backend down → `"backend unreachable"` with `role="alert"` on the label. |

---

## View 3 — Case Map (`components/CaseMap.jsx`)

MapLibre GL map centered on Puerto Rico (zoom 8.2), rendering case dots
colored by evidence tier over a bundled municipio-outline layer plus an OSM
raster basemap.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Zoom-in button | button (MapLibre `NavigationControl`, built-in) | `+` | Native MapLibre zoom-in; `showCompass: false` so only zoom buttons render. | **Live** | Present and clickable; triggered without error. |
| Zoom-out button | button (MapLibre `NavigationControl`) | `−` | Native MapLibre zoom-out. | **Live** | Same as above. |
| Scroll-wheel zoom / drag-to-pan | gesture (MapLibre built-in) | — | Default MapLibre interaction handlers. | Static (not exercised — Playwright wheel/drag emulation not run) | Standard library behavior, not custom app code. |
| Click a case dot | click handler on `cases-dot` layer | — | `map.on('click', 'cases-dot', e => onSelectRef.current?.(e.features[0].properties))` → `Dashboard`'s `selectByProps`, which looks the full case up by `case_id` in the already-fetched `cases` list (falling back to the map feature's own properties if not found) and calls `setSelected`, opening the Case Detail sheet. | **Live** (handler path confirmed; see Case Detail below for the rendering defect it triggers) | Cursor changes to pointer on hover over a dot (`mouseenter`/`mouseleave` handlers). |
| Basemap raster tiles (OpenStreetMap) | passive resource, not a control | — | `tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png']` | **Static-only: requires internet access to tile.openstreetmap.org** | This sandbox has no route to that host — tile requests fail with `net::ERR_CONNECTION_RESET` (visible in the browser console). This is an environment limitation, not an app bug; `desktop/README.md` documents the same offline caveat ("map basemap tiles are fetched from the internet… without a connection the map background is blank while all data, tables, and charts keep working"). |
| Municipio outlines / case dots (GeoJSON layers) | passive resource | — | Loaded from bundled `public/geo/pr_municipios.geojson` and the `/geojson` API route (`releases/<date>/ovnis_cases_master.geojson`). | **Live** | Rendered correctly whenever the map's flex container is normal-sized (Statistics/Candidates tabs active). **Broken when the Cases tab is active** — see finding below. |

### ⚠️ Finding: map renders as an invisible sliver whenever the Cases tab is active

Root cause is shared with the Case Detail finding below (missing Tailwind
zero-value utilities) and is described once, under Case Detail, to avoid
duplication. Screenshot evidence: `04-cases-tab.png` (map area solid black,
no dots/outlines visible) vs. `02-stats-tab.png`/`03-candidates-tab.png` (map
renders correctly) captured seconds apart in the same session, tab switch
being the only variable.

---

## View 4 — Tab navigation (`pages/Dashboard.jsx`, lines 53–58; `components/ui/tabs.jsx`)

Three-way tab switch (Radix `Tabs`) for the right-hand panel.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Cases" tab | tab trigger | Cases | `TabsTrigger value="cases"` → shows `CaseGrid`. Default active tab. | **Live** | Confirmed. |
| "Statistics" tab | tab trigger | Statistics | `TabsTrigger value="stats"` → shows `StatsPanel`. | **Live** | Confirmed; also confirmed the map renders correctly while this tab is active (see finding above). |
| "Candidates" tab | tab trigger | Candidates | `TabsTrigger value="candidates"` → shows `CandidateReview`. | **Live** | Confirmed. |

---

## View 5 — Cases tab (`components/CaseGrid.jsx`)

All 470 master cases in a sortable-by-filter table. Filtering is entirely
client-side against the already-fetched `cases` array (no server round-trip
per keystroke/selection) — `useCases()` fetches `GET /cases` once and
`CaseGrid` narrows it with local `useState`/`.filter()`.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Search input | text input | placeholder `Search…` | `onChange={e => setQ(e.target.value)}`; filters `cases` client-side where `q` is a case-insensitive substring of `description` or `locString(c)`. | **Live** | Typed `"Arecibo"` → row count dropped from 470 to 19. Cleared → back to 470. |
| Decade select | dropdown (shadcn `Select`) | `All decades` / `1920s`…`2020s` | `onValueChange={setDecade}`; options built from `Array.from(new Set(cases.map(c => c.decade)))`. Filters rows to `c.decade === decade`. | **Live** | Opened the list (12 options: `All decades` + `1920s`…`2020s`), selected `1920s` → 7 rows; reset to `All decades` → 470 rows. |
| Tier select | dropdown (shadcn `Select`) | `All tiers` / `T1`/`T2`/`T3`/`T4` | `onValueChange={setTier}`; filters rows to `c.evidence_tier === tier`. | **Live** | Selected `T1` → 3 rows; reset to `All tiers` → 470 rows. |
| Table row click | row click handler (all 470 rows) | case row (`case_id`, date, location, agency, tier columns) | `onClick={() => onSelect?.(c)}` → `Dashboard`'s `setSelected(c)`, opening the Case Detail sheet with the full record. | **Live** (opens the sheet's state correctly; see the rendering defect under Case Detail) | Selected row gets a violet highlight (`bg-violet-500/10`); rows from a military/agency `source_family` get a subtle tint instead when not selected. |
| "No URL" badge (per row) | static badge, not clickable | `No URL` | Rendered via `hasSourceUrl(c)` when the case has no browser-safe `source_url`. Purely informational (also has a `title="source has no URL"` tooltip). | **Live** | Visible on many rows (e.g. `PRUAP-0002`). |
| No-coordinates icon (per row) | static icon, not clickable | `MapPinOff` icon | Rendered via `!hasCoords(c)`; purely informational. | Static | Not separately exercised beyond visual confirmation. |

### ⚠️ Finding: Cases tab's table has no internal scroll boundary — it forces the whole page to ~11,300px tall

**Root cause (confirmed by inspecting the actual compiled CSS the dev server
serves):** this repo recently bumped Tailwind CSS from 3.4.19 to 4.3.3 (see
`dashboard/package.json` git history). `dashboard/src/index.css` still loads
the old v3-style config via `@config "../tailwind.config.js"` for backward
compatibility. Under this build, **every Tailwind utility whose value is the
bare number `0` on the spacing/inset scale fails to generate any CSS at
all** — confirmed by grepping the served stylesheet: `.min-h-0`, `.min-w-0`,
`.inset-0`, `.inset-x-0`, `.inset-y-0`, `.top-0`, `.right-0`, `.bottom-0`,
`.left-0`, `.p-0`, `.m-0`, `.gap-0` etc. are **entirely absent**, while every
non-zero and arbitrary-value variant (`.h-full`, `.top-full`, `.top-\[1px\]`,
`.top-\[50%\]`, …) compiles fine.

`Dashboard.jsx`'s map/sidebar row (`<div className="flex flex-1 min-h-0">`)
and the Cases tab's own `TabsContent` (`flex-1 min-h-0`) both rely on
`min-h-0` to stop a flex child from growing to fit its content and instead
respect the `h-screen` ancestor — that's precisely the CSS rule that is now
silently missing. With it gone, whenever the Cases tab's ~470-row,
non-virtualized `<Table>` is in the DOM, its natural (unclamped) height
becomes the *minimum* height of the whole flex row, and — because flex items
default to `align-items: stretch` — the map pane is stretched to match. Live
measurement: `document.documentElement.scrollHeight` was **11,391px** on a
900px-tall viewport while the Cases tab was active. The result: the map
canvas gets an internal backing-store resolution of 357×4096 (WebGL's
max-texture-size clamp) displayed at 983×11,278 CSS pixels, so the visible
900px viewport shows only the very top sliver of it — which reads as a
uniform black rectangle (screenshot `04-cases-tab.png`) — and the case table
never gets its intended fixed-height scrollable panel; it just keeps
extending the page.

Switching to the Statistics or Candidates tab (whose `TabsContent` doesn't
contain the big table) immediately restores the correct ~900px layout and a
correctly rendered map (screenshots `02-stats-tab.png`, `03-candidates-tab.png`)
— confirming the giant table is what's forcing the blow-up, not a one-off
map/WebGL issue.

**User impact:** on the default (Cases) tab, the map is functionally
invisible and the page requires scrolling ~11,000px to see all case rows
instead of scrolling a small internal table panel. This is a real, currently
broken control, not a hypothetical — it's the tab a user lands on by default.

---

## View 6 — Case Detail sheet (`components/CaseDetail.jsx`, `components/ui/sheet.jsx`)

A right-side drawer (shadcn `Sheet`, built on Radix `Dialog`) showing the
full record for whichever case was selected from the map or the table.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Sheet open/close state | Radix `Dialog` root | — | `<Sheet open={!!c} onOpenChange={o => !o && onClose?.()}>` — opens whenever `Dashboard`'s `selected` state is non-null. | **Live** — opens correctly at the React/DOM level (`data-state="open"`, correct case content populated) | See the rendering defect below: the panel itself is not visible on screen. |
| Close "✕" button | button (built into shadcn `SheetContent`) | (icon only, `sr-only "Close"`) | `SheetClose` → Radix `Dialog.Close`, sets `open=false` → `onClose()` → `setSelected(null)`. | **Live, but only reachable via mouse in theory** — see defect below | Playwright's actionability check reported *"Element is outside of the viewport"* when attempting a real click; closing only succeeded via the `Escape` key (a global keydown listener, independent of the element's CSS position). |
| Click outside / overlay | Radix `Dialog` default dismiss | — | Clicking the dark overlay behind the sheet calls `onOpenChange(false)`. | Static-only (overlay is also mispositioned — see below; not separately clicked) | |
| External source link | link (`<a target="_blank" rel="noopener noreferrer">`) | source citation / URL text, with an `ExternalLink` icon | Rendered only when `sourceUrl(c)` returns a browser-safe `http(s)` URL (deliberately excludes legacy rows that store plain citation text in `source_url` — see `ovnis-format.js` comment). Opens the source in a new tab. | **Live** | Confirmed on `PRUAP-0001`: link text `"Ships and Sugar..."`, `href="https://archive.dartmouthalumnimagazine.com/article/1954/2/1/ships-and-sugar-an-evaluation-of-puerto-rican-offshore-shipping"`. Correctly `target="_blank"`. |
| "No URL" badge (in sheet) | static badge | `No URL` | Shown instead of a link when the case has no safe URL. | Static | Not separately re-verified (identical logic to the grid badge, already confirmed there). |

### ⚠️ Finding: the Case Detail drawer renders completely off-screen and is unusable by mouse

Same root cause as the Cases-tab finding above (Tailwind v4 build silently
dropping every bare-zero spacing/inset utility) — confirmed independently for
this component. `SheetContent`'s `side="right"` variant is
`inset-y-0 right-0 h-full … w-full sm:max-w-md` on a `position: fixed`
element. With `inset-y-0`/`right-0` generating no CSS, the browser falls back
to the element's **static-flow position** (as if it were `position: static`),
placing it right after the ~900px-tall app root in the *document* flow.

Live measurement immediately after opening the sheet (viewport 1440×900):

```
{
  "position": "fixed",       // the *class* fixed still applies — position itself isn't the problem
  "rect": { "x": 8, "y": 908, "w": 1441, "h": 900 },
  "top": "908px", "bottom": "-908px", "right": "-9px",
  "dataState": "open"
}
```

`y: 908` on a 900px-tall viewport means the entire panel — and its dark
backdrop overlay, independently confirmed to have collapsed to a `0×0` box
for the same reason — renders **entirely below the visible viewport**. The
sheet is logically open (correct data, correct `data-state`) but there is
nothing to click: Playwright's real-click attempt on the close button failed
with *"Element is outside of the viewport,"* and only `Escape` (a global
Radix keydown handler that does not depend on layout) successfully closed
it. A real mouse user opening a case from the map or the table would see no
visible change on screen at all.

**Combined severity note.** These two findings (Cases-tab layout collapse,
Case Detail drawer invisibility) both stem from the same one-line-traceable
regression — the Tailwind 3→4 upgrade plus the legacy `@config` shim
silently discarding zero-value spacing utilities — and together affect two
of this small app's most central interactions: the default tab's primary
map view, and the one modal/detail flow the whole app has. They were not
guessed at; both were reproduced live and the missing CSS rules were
confirmed by inspecting the actual stylesheet the dev server serves.

---

## View 7 — Statistics tab (`components/StatsPanel.jsx`)

Read-only KPIs and two Recharts bar charts, from `GET /stats`.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| KPI tiles (Total/Mapped/Unmapped) | static display, not interactive | `Total` / `Mapped` / `Unmapped` | Rendered from `useStats()`. | **Live** | Confirmed values `470 / 469 / 1` matched `/health` and `/stats`. |
| "Cases by decade" bar chart | Recharts `BarChart` + hover tooltip | — | `Tooltip` shows per-bar values on hover; no click behavior. Bars colored `#a78bfa`. | Static (hover not exercised) | Chart container renders (`ResponsiveContainer`); not separately screenshotted mid-hover. |
| "Cases by evidence tier" bar chart | Recharts `BarChart` + hover tooltip | — | Same as above; bars colored per-tier via `tierHex()` (`Cell` per bar). | Static (hover not exercised) | |
| `QueryState` Retry button | button | Retry | Shown only when `isError` is true; `onClick={onRetry}` → react-query's `refetch()`, re-running `GET /stats`. | **Live** | Confirmed with the backend intentionally stopped: `"Could not load this data"` message appeared with a visible Retry button; clicking it re-issued the request (still failed, as expected, since the backend was still down) without throwing. |

---

## View 8 — Candidates tab (`components/CandidateReview.jsx`)

Read-only intake queue (`GET /candidates`) — no promote/reject actions exist
in this UI (the repo's promotion pipeline is a CLI script,
`scripts/promote_candidate.py`, not exposed here).

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| Candidate list | static display, not interactive | `N candidates in queue` + per-candidate cards | Rendered from `useCandidates()`. Status badge color comes from `federationTone()` mapped through `STATUS_ROLE`. | **Live** | Confirmed with the bundled data: `"1 candidates in queue"`, one card (`CAND-0000`, tier `T4`, status `pending`, a placeholder row per its own description text — "Placeholder candidate row used only to keep schema validation wired before real candidate intake is..."). |
| `QueryState` Retry button | button | Retry | Same pattern as Statistics tab; `onClick={onRetry}` → `refetch()` for `GET /candidates`. | **Live** | Confirmed with backend down: error message + visible, clickable Retry button. |
| `FederationEmptyState` (empty queue) | static display | "Queue empty" | Rendered only when the fetch succeeds **and** the array is empty — deliberately distinct from the error state (source comment explains this was previously conflated, silently showing "Queue empty" during a real outage). | Static-only (current data has 1 candidate, so this state wasn't reached) | Not a bug — just not exercised because the bundled data always has at least one row. |

---

## View 9 — 404 / Not Found (`lib/PageNotFound.jsx`)

Rendered by the catch-all `<Route path="*">`.

| Element | Type | Label | Handler/Behavior | Verified | Notes |
|---|---|---|---|---|---|
| "Go Home" button | button | Go Home | `onClick={() => (window.location.href = '/')}` — full page navigation back to `/`. | **Live** | Navigated to `/does-not-exist` → confirmed `"404 / Page Not Found / The page "does-not-exist" could not be found."`; clicked Go Home → URL returned to `http://127.0.0.1:5175/` and the dashboard re-rendered. |

---

## Unused shadcn/ui primitives (present in `components/ui/`, not wired into any current view)

The following components exist under `dashboard/src/components/ui/` and are
part of the shadcn/ui library scaffold, but nothing in `pages/` or the
app-level `components/` currently imports them. They are effectively
inert/dead in the running app today (no route, tab, or state renders them),
so no interactive elements from these files are counted in the summary below.
Listed for completeness per the request to audit `components/` as thoroughly
as `pages/`.

`accordion.jsx`, `alert-dialog.jsx`, `alert.jsx`, `aspect-ratio.jsx`,
`avatar.jsx`, `breadcrumb.jsx`, `calendar.jsx`, `carousel.jsx`, `chart.jsx`,
`checkbox.jsx`, `collapsible.jsx`, `command.jsx`, `context-menu.jsx`,
`dialog.jsx`, `drawer.jsx`, `dropdown-menu.jsx`, `form.jsx`, `hover-card.jsx`,
`input-otp.jsx`, `menubar.jsx`, `navigation-menu.jsx`, `pagination.jsx`,
`popover.jsx`, `progress.jsx`, `radio-group.jsx`, `resizable.jsx`,
`scroll-area.jsx`, `sidebar.jsx`, `slider.jsx`, `switch.jsx`, `textarea.jsx`,
`toggle-group.jsx`.

Actually used by the live app: `badge.jsx`, `button.jsx` (transitively, via
other primitives), `input.jsx`, `label.jsx` (transitively), `select.jsx`,
`sheet.jsx` (→ `dialog.jsx`'s Radix primitive, not the `dialog.jsx` wrapper
file itself), `table.jsx`, `tabs.jsx`, `toast.jsx`/`toaster.jsx`/`use-toast.jsx`
(mounted but never triggered), `tooltip.jsx` (used internally by Recharts'
chart tooltip wiring / other primitives), `separator.jsx`, `skeleton.jsx`,
`toggle.jsx` — several of these are pulled in transitively by the primitives
above rather than imported directly by app code.

Also unused: the `search()` function and `/search` backend route
(`dashboard/src/lib/api.js` exports `search(q)` hitting `GET /search`) are
never called from any component — `CaseGrid`'s search box filters the
already-fetched case list client-side instead. Not a bug, just dead code
worth flagging.

---

## Desktop Launcher

Read: `desktop/launch.py`, `desktop/app_server.py`, `desktop/config.py`,
`desktop/setup.py`, `PRII-OVNIS.command`, `PRII-OVNIS.sh`, `PRII-OVNIS.bat`,
`PRII-OVNIS.app/Contents/MacOS/PRII-OVNIS`.

**What happens when a user double-clicks a launcher:**

1. **Platform launcher script** (`PRII-OVNIS.command` macOS /
   `PRII-OVNIS.sh` Linux / `PRII-OVNIS.bat` Windows, or the `.app` bundle's
   `Contents/MacOS/PRII-OVNIS` shell script on macOS Finder) `cd`s to the
   repo root, locates a `python3`/`python` interpreter, and runs
   `python desktop/setup.py --ensure`.
   - The `.app` variant additionally detects macOS Gatekeeper's
     "App Translocation" (a quarantined `.app` opened from a random
     read-only temp path with the rest of the checkout missing) and shows a
     native `osascript` dialog explaining the fix (move the folder, run
     `Fix-Gatekeeper.command`) instead of a confusing generic failure.
2. **`desktop/setup.py`** (idempotent, marker-file-gated;
   `.setup-complete` + presence of the venv + built `dist/index.html`):
   - Creates a private `.venv` at the repo root (`venv.EnvBuilder`).
   - `pip install`s `server/backend/requirements.txt` (FastAPI, uvicorn) and
     `requirements-desktop.txt` (`pywebview`, plus the pinned
     `prii-desktop` package fetched via `git+https://github.com/jotaele44/thehub-pr.git@<pinned-commit>#subdirectory=packages/prii_desktop`).
   - Builds the dashboard: `npm ci`/`npm install` then `npm run build` in
     `dashboard/`, with `VITE_API_BASE=""` so the built SPA calls the API
     same-origin (no CORS needed once served by the desktop wrapper).
   - Fails loudly (raises `SystemExit` with a clear message) if `npm` is
     missing or the build doesn't produce `dashboard/dist/index.html`.
3. **`desktop/launch.py`** then runs (`.venv`'s python interpreter): a thin
   shim that calls into the shared `prii_desktop.launch(DesktopConfig.from_module(config))`.
   Per its own docstring, the actual runtime (uvicorn startup, native window,
   single-instance lock, `--smoke` CI mode) lives in that shared package, not
   in this repo. `desktop/config.py` supplies this repo's specifics: app
   title `"OVNIS"`, `APP_IMPORT = "server.backend.main:app"`, frontend/dist
   paths, and the `/health` path used to detect the backend is up.
   `desktop/app_server.py` (imported by the shared launcher) wraps the same
   FastAPI app with `make_desktop_app`, additionally serving the built Vite
   `dist/` from the same port — one process, no CORS.
   - Net effect (from the config + docstrings, since `prii_desktop` itself
     lives in a sibling repo not checked out here): picks a free local port,
     starts a same-origin uvicorn server serving both the API and the built
     SPA, and opens a native `pywebview` window pointed at it (falling back
     to the system default browser if `pywebview` / a native webview isn't
     available). Supported flags: `--no-window` (server only, for
     scripting/CI), `--browser` (force default browser instead of a native
     window), `--route PATH` (open a specific route), `--smoke` (CI
     smoke-test mode — start, verify health, exit).
4. **First run** requires internet once (to `pip install` and `npm install`,
   plus resolving the `prii-desktop` git dependency); **every later run**
   starts instantly and works fully offline against the data already
   committed to the repo, **except** the OSM basemap raster tiles on the map
   (documented in `desktop/README.md`'s "Offline caveat" — data, tables, and
   charts all still work without a connection).

**Not independently live-tested in this audit**: the desktop launcher path
itself was not run end-to-end, because `prii_desktop` (the actual
runtime/window code) is fetched from the sibling `thehub-pr` repository via a
pinned git+pip dependency, which is out of scope for a cheap/fast check per
the task's guidance not to chase a full external dependency chain. The
FastAPI backend it wraps (`server/backend/main.py`) is identical to the one
this audit *did* run and verify live (see Overview); the desktop-specific
delta is same-origin serving of the built SPA plus the native window shell,
which are implemented entirely in the external `prii_desktop` package.

---

## Summary

- **Pages/views audited:** 9 (App Shell, Header, Case Map, Tab navigation,
  Cases tab/CaseGrid, Case Detail sheet, Statistics tab, Candidates tab,
  404), plus the Desktop Launcher entry points and a full pass over all 49
  files in `components/ui/` to confirm which are live vs. unused.
- **Total interactive elements cataloged:** 23 (in the live-reachable app
  surface; unused shadcn/ui primitives and their internal controls are
  listed separately and not included in this count, since no current view
  renders them).
  - **Live-verified:** 17
  - **Static-only** (documented from source, not exercised — mostly because
    they require an unavailable external service, a forced error condition,
    or a hover-only interaction not exercised in this pass): 6
    (`ErrorBoundary` "Try again", basemap raster tiles, scroll/drag map
    gestures, two chart tooltips, click-outside-to-dismiss on the Case
    Detail overlay, `FederationEmptyState` empty-queue state — several of
    these are effectively unreachable/uninteresting for a live check rather
    than blocked by missing credentials).
- **Broken/dead controls found:**
  1. **Cases tab — map renders invisible and the case table has no scroll
     boundary**, forcing the whole page to ~11,300px tall on a 900px
     viewport. Reproduced live; root-caused to the Tailwind 3→4 dependency
     bump silently dropping every bare-zero spacing/inset utility
     (`min-h-0`, `min-w-0`, …) from the compiled CSS. See **View 5** finding.
  2. **Case Detail drawer (opened from a map click or a table row) renders
     completely off-screen and is unusable by mouse** — same root cause,
     confirmed independently (`inset-y-0 right-0` resolving to no offset at
     all). Only the `Escape` key closes it; the visible close button and
     click-outside-to-dismiss are both unreachable. See **View 6** finding.
  3. (Latent/dormant, not separately broken but sharing the same root cause)
     the `Toaster`/toast notification container uses the same class of
     zero-value utilities (`fixed top-0 … sm:bottom-0 sm:right-0`) and would
     likely render mispositioned if any future code path calls `toast()` —
     nothing currently does.
  - No dead JavaScript event handlers (`onClick`/`onChange`/etc. wired to
    nothing, or throwing) were found. Every control's *logic* worked as
    coded; the defects found are exclusively a CSS build regression, not
    broken application code.
