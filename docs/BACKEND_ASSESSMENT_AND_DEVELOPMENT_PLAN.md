# Backend Assessment & Development Plan — ovnis-pr

## Scope & method

Read-only assessment of the backend at `main` (`68b8736`, "Mark normalized roadmap snapshot
audit-only"). `ovnis-pr` is the historical anomalous-event case-corpus producer node in the
PRII federation: it maintains a reviewed ledger of historical anomalous-event cases tied to
Puerto Rico municipios, plus a federal/military-installation cross-reference subsystem
("fedmil"), and exports a federation package to `thehub-pr`. Of the six producers, this one
is the most "done" by its own honest self-assessment — `federation.json` reports
`production_status: PRODUCTION`, `ready_for_hub_live_execution: true`, and an **empty**
`blocking_conditions` list.

## Tech stack & backend inventory

- **Framework**: single-file FastAPI app, `server/backend/main.py` (11 KB) — the simplest
  backend of the six producers.
- **Storage**: pure JSONL ledgers — `data/master/master_cases.jsonl` (591 KB, real,
  non-placeholder data) and `data/candidates/candidate_cases.jsonl` — plus GeoJSON releases
  under `releases/`.
- **Endpoints** — entirely read-only, no POST/PATCH/DELETE anywhere, no auth dependency
  (appropriate since there is nothing mutable to protect): `/health`, `/cases`
  (filter by decade/tier/municipality/query), `/cases/{case_id}`, `/candidates`
  (read-only listing — no way to act on a candidate via the API), `/geojson` (serves the
  latest release or derives points live from the master ledger as fallback), `/stats`,
  `/search`.
- The module docstring states its own honesty policy: it does not infer production case
  counts from README copy, it reports the actual files on disk — including a
  `placeholder_only` state via `is_placeholder()`/`data_status()` if that's what's there.
- **No write/review API**: candidate→master promotion happens entirely offline via
  `scripts/promote_candidate.py`, `dedupe_candidates.py`, `score_candidates.py`, and
  human-reviewed PRs (per `federation.json`: "Automated ingestion writes only to the
  candidate ledger; master promotion occurs through reviewed PRs"). This is a deliberate
  git-as-audit-trail design choice, not an oversight.
- **Domain scripts**: `scripts/import_candidates.py`, `import_prufon_legacy.py`
  (14.6 KB — migrating a legacy "PRUFON" dataset; `federation.json` records
  `repository_legacy_name: "PRUFON"`), `consolidate_prufon_sources.py`,
  `fedmil_context_export.py` / `fedmil_review_queue.py` / `fedmil_roundtrip.py` (a
  federal-military-context cross-reference subsystem), `validate_case_ledgers.py`,
  `validate_fedmil_context.py`.
- **Background jobs**: none in-process; scheduled via GitHub Actions
  (`candidate-intake.yml`, `maintenance.yml`).
- **Tests/CI**: 17 test files — the smallest suite of the six producers, proportionate to
  the smaller backend surface, though the fedmil/prufon subsystems have comparatively thin
  coverage relative to their apparent complexity. 15 CI workflows (`ci.yml`,
  `candidate-intake.yml`, `codeql.yml`, `gui-capability-parity.yml`, `foia-canary-*`,
  `semgrep.yml`, `validate.yml`).

## Completion assessment

- **Fully implemented and self-declared production-ready**: the master ledger contains
  real, non-placeholder data; the read API is complete for its stated scope. No
  TODO/FIXME/stub/placeholder-code markers found in code search.
- **Missing relative to sibling producers, by design**: no API-driven review/promotion
  workflow (candidates can only be read, not acted on, through the API); no write endpoints
  of any kind; no auth layer (fine given nothing is mutable, but means a future write API
  would need auth built from scratch, unlike `aguayluz-pr`/`moneysweep-pr` which already
  have scaffolding).
- **Invisible to the API**: the `fedmil_context` subsystem is scripted and produces real
  output (`data/fedmil_context/`), but has no corresponding FastAPI router — dashboard and
  API consumers cannot query it today, only offline script runs touch it.

## Development plan — hardest tasks first

Ordering rationale: items 1–2 are sequenced first because each is a from-scratch
architectural decision (new auth model, or a new API surface over an existing but
API-invisible subsystem) rather than a bounded fix — getting the design right up front
avoids rebuilding a review workflow or an API contract later. Items 3–4 are then
data-correctness/completeness work that can proceed independently.

1. **Build an API-driven review/promotion workflow**, if candidate cases are ever meant to
   be triaged from the dashboard instead of via git PRs — Effort: **XL**. From-scratch
   feature requiring new auth (this repo has none today), new write endpoints, and a policy
   decision on whether the current "promotion via reviewed PR" audit-trail model should be
   preserved alongside it or replaced. Should reuse whatever federation-wide auth contract
   `thehub-pr` ships (see that repo's plan doc) rather than inventing a local one.
2. **Expose the fedmil_context subsystem via API** — Effort: **L**. `fedmil_context_export.py`
   / `fedmil_review_queue.py` / `fedmil_roundtrip.py` exist as scripts with no FastAPI
   router; wiring this in requires understanding an already-built but API-invisible
   cross-reference model (federal/military installation proximity to cases) and deciding
   its read/write semantics before writing the router.
3. **Legacy PRUFON data migration completeness** — Effort: **M**, one-off. Verifying
   `import_prufon_legacy.py` (14.6 KB) has fully reconciled any schema drift between the
   legacy dataset and the current `case.schema.json` is inherently a detail-heavy,
   hard-to-automate data-migration task.
4. **Geocoding/coordinate resolution for unmapped cases** — Effort: **M**. `main.py`'s
   `/stats` already tracks `mapped` vs `unmapped` cases and gracefully falls back to
   deriving GeoJSON from the master ledger. Closing the gap for cases lacking lat/lon needs
   a geocoding pipeline against the PR municipio/feature gazetteer referenced elsewhere in
   the federation — this doesn't exist yet and is a real integration task, not a lookup.
5. **Deepen test coverage for the fedmil/prufon subsystems** — Effort: **M**, diffuse. Only
   17 test files total, several (`test_fedmil_*`, `test_prufon_legacy_contract.py`) covering
   comparatively complex historical cross-referencing logic — a real risk of undetected
   regressions as this narrower area evolves, though not "hard" in a single-task sense.

## Quick wins (sequenced after/alongside the above, not skipped)

- None of the incompleteness signals here are urgent — this is the most "done" repo in the
  federation by its own self-assessment. The lowest-effort improvement available: add a
  thin read-only `/fedmil` endpoint to at least surface `data/fedmil_context/` output
  through the API, since the data and logic already exist as scripts (a small first step
  toward item 2 above, not a substitute for it).
