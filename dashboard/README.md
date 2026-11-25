# OVNIS Dashboard (Ovnis-PR)

> **Diagnostic-only surface (ADR 0001, Phase 2).** This dashboard is a
> development and diagnostic tool for this producer only. The supported product
> surface for the PRII federation is the hub app
> (`thehub-pr/server/frontend`), which renders this producer's data alongside
> the other engines. See `thehub-pr/docs/adr/0001-federated-engines-single-hub.md`.

Local-only React dashboard for the OVNIS UAP sighting registry. Same federation
frontend process — Vite + React (JSX) + Tailwind + shadcn/ui + react-query,
Auth stripped. **MapLibre GL** renders the sighting map.

## Run

```bash
# 1. Backend (from repo root) — thin FastAPI over the JSONL ledgers + GeoJSON, on :8000
pip install -r server/backend/requirements.txt   # fastapi, uvicorn (stdlib otherwise)
uvicorn server.backend.main:app --reload --port 8000

# 2. Frontend (this dir) on :5173
npm install
npm run dev
```

Open http://localhost:5173. (`VITE_API_BASE` overrides the API base; default
`http://localhost:8000`.)

## What it shows
- **Map** — the 364 mapped sightings from the release GeoJSON, colored by
  evidence tier (T1→T4). Click a point to open the case detail.
- **Cases** — all **470** master cases (the ~106 without coordinates are kept and
  flagged with a "no coordinates" icon). The search box matches case id, year /
  date, decade, description, place and agency; the period (decade) and tier
  filters narrow it further, active filters show as removable chips, and the
  list is paginated (12 per page by default; 12 / 24 / 48 / 100). A search that
  matches nothing shows "No cases found" with a **Reset search** button.
- **Statistics** — total / mapped / unmapped KPIs, cases-by-decade and
  cases-by-tier charts (recharts).
- **Candidates** — the candidate intake queue awaiting promotion.
- **Activity** — the program timeline.

## Layout: desktop and mobile
The shell switches at **860 CSS px** (the federation GUI spec's mobile
breakpoint; `MOBILE_BREAKPOINT` in `src/hooks/use-mobile.jsx` and the
`shell-mobile` / `shell-desktop` variants in `src/index.css` must stay in step).

| | Desktop (≥ 860px) | Mobile (< 860px) |
|---|---|---|
| Navigation | tabbed 440px side pane beside the map | bottom nav: Cases · Map · Statistics · Candidates · **More** (Activity, backend status) — never more than five |
| Cases | table | touch cards; filters on labelled 44px fields |
| Case detail | right-hand drawer | bottom sheet (≤ 85% of the screen) |
| Header | brand + health + controls | 54px + top safe area; health collapses to its dot |

Touch targets on the mobile shell are at least 44px, the document never scrolls
sideways, `viewport-fit=cover` plus `env(safe-area-inset-*)` keep content clear
of the notch and home indicator, and landscape phones (< 500px tall) put the
case filters on one row. Toasts sit above the bottom nav on mobile.

## Theme and language
- **Theme** — the header button cycles dark (default) → light → system. The
  choice is stored in `localStorage` (`ovnis.theme`) and applied before first
  paint. Light mode remaps the slate colour scale in `src/index.css` rather than
  restyling each component.
- **Language** — the 🇺🇸 / 🇵🇷 buttons switch English / Spanish (stored as
  `ovnis.locale`; defaults to the device language). Strings live in
  `src/lib/locale.js`; a test fails if a key exists in one language but not the
  other. The shell, navigation, Cases list and case detail are translated; the
  Statistics, Candidates and Activity panels are not yet.

## Native wrapper (Capacitor)
`ios/` and `android/` wrap the **offline** build (`VITE_OFFLINE=1`, output
`export-standalone/`, data baked in from `src/lib/snapshot.json`) with Capacitor
8. The app id `pr.ovnis.app` is a placeholder — set the real one in
`capacitor.config.json` (and re-run `npx cap sync`) **before** publishing, since
store bundle ids cannot be changed later.

```bash
npm run cap:sync      # offline build + copy into ios/ and android/
npm run cap:ios       # ...then open Xcode   (macOS only)
npm run cap:android   # ...then open Android Studio
```

Launcher icons and splash screens were generated from
`assets/branding/icon.png`. Synced web assets (`ios/App/App/public`,
`android/app/src/main/assets/public`) are git-ignored. Native builds, signing
and on-device checks (safe areas, status bar, keyboard) have **not** been run.

## Tests
`npm test` (vitest, including axe checks on the mobile list, nav and controls)
and `npm run test:gui-parity` (Playwright against the real backend: the desktop
spec plus `tests/gui-parity-mobile.spec.mjs` at 390×844, 430×932 and 844×390).
Emulated viewports are not a physical iPhone run.

## Backend (`server/backend/main.py`)
Reads `data/master/master_cases.jsonl`, `data/candidates/candidate_cases.jsonl`,
and the latest `releases/*/ovnis_cases_master.geojson` (stdlib json/csv — no DB,
the Git files are the authority). Lists/stats include unmapped cases; `/geojson`
serves only the 364 mapped features. CORS allows `:5173`.
