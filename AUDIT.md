# Fed Repos — Backend & Frontend Completion Audit

**Date:** 2026-09-21  
**Branch:** `claude/completion-audit-fed-repos-3gkse9`  
**Scope:** All 7 federated repositories under `jotaele44`

---

## Summary

| Metric | Value |
|---|---|
| Repos audited | 7 |
| Backend complete (substantial) | 5 (moneysweep, aguayluz, skywatcher, thehub + partial spiderweb) |
| Frontend complete (rich) | 4 (centinelas, skywatcher, spiderweb, thehub) |
| Critical gaps | 4 items (centinelas BE, ovnis BE, spiderweb production.py, aguayluz generated/) |
| Moneysweep test suite | 2394 passing · 51.7% coverage (gate: 44%) |

---

## This Repo: ovnis-pr

**Backend: Minimal** — Single `main.py` (17KB) only. No domain-specific API modules beyond it. Uses `requirements.lock` instead of `uv.lock`.

**Correction (2026-09-23):** an earlier version of this section claimed CaseMap/SpatialToolsPanel
have no backend counterpart and that there were no backend test files — both were wrong.
`server/backend/main.py` implements a `/municipios/case_density` endpoint that does
point-in-polygon geometry against municipio boundaries — exactly the kind of spatial data
CaseMap.jsx and SpatialToolsPanel.jsx would consume — and it is directly exercised by
`tests/test_server_smoke.py` and `tests/test_municipios_case_density.py`. Other frontend
pages/components may still lack backend coverage; that was not re-verified here.

**Critical gaps:**
- `requirements.lock` diverges from fleet toolchain (uv) — should migrate to uv

**Frontend: Component-rich, page-sparse** — 1 page (`Dashboard.jsx`) despite rich spatial components.

Components: `CaseMap.jsx` (19.5KB), `SpatialToolsPanel.jsx` (13.5KB), `CaseDetail.jsx`, `CaseGrid.jsx`, `StatsPanel.jsx`, `CandidateReview.jsx`. Tests present on CaseDetail, QueryState, SpatialToolsPanel.

**Gap:** CandidateReview → CaseDetail case workflow routing layer missing. Rich components built but not wired to pages.

---

## Priority Actions for ovnis

1. **HIGH** — Implement domain API modules for Case management and Spatial endpoints
2. **HIGH** — Migrate from `requirements.lock` to `uv.lock` (align with fleet)
3. **MEDIUM** — Add page routing: wire CandidateReview, CaseDetail, CaseGrid to dedicated pages
4. **MEDIUM** — Extend backend test coverage beyond `/municipios/case_density` (see correction above; `test_server_smoke.py` and `test_municipios_case_density.py` already cover that endpoint)

---

See full fleet audit: https://claude.ai/artifact/G8dsMnxcTN8ouJaaQrULF2

*Audit date: 2026-09-21*
