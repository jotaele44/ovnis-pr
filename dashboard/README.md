# OVNIS Dashboard (Ovnis-PR)

Local-only React dashboard for the OVNIS UAP sighting registry. Same federation
frontend process — Vite + React (JSX) + Tailwind + shadcn/ui + react-query,
Base44 auth stripped. **MapLibre GL** renders the sighting map.

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
  flagged with a "no coordinates" icon). Filter by decade / tier, search.
- **Statistics** — total / mapped / unmapped KPIs, cases-by-decade and
  cases-by-tier charts (recharts).
- **Candidates** — the candidate intake queue awaiting promotion.

## Backend (`server/backend/main.py`)
Reads `data/master/master_cases.jsonl`, `data/candidates/candidate_cases.jsonl`,
and the latest `releases/*/ovnis_cases_master.geojson` (stdlib json/csv — no DB,
the Git files are the authority). Lists/stats include unmapped cases; `/geojson`
serves only the 364 mapped features. CORS allows `:5173`.
