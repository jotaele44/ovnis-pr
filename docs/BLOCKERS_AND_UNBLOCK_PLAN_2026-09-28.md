# Blockers and unblock plan — ovnis-pr (2026-09-28)

**Audit date:** 2026-09-28 · **`main` at audit:** `4b4a53a` (not branch-protected) · **Production status:** `PRODUCTION` (470-case master corpus)

**Post-audit update (2026-09-28 20:35Z):** the record_cell_binding v0.2 series was pushed straight to `main` after the audit. The Cell_Set PR #160 now conflicts with `main` and is superseded (X-05). The same series left `ruff check .` red on `main` (X-10); this PR carries the one-line fix.

This document lists every blocker that the repository, its CI, and its GitHub issues and pull requests recorded as of the audit date, then gives an ordered plan to clear them. It changes no code, gate, ledger, or status file.

Cross-repository blockers (IDs `X-nn`) are described in full in
`jotaele44/thehub-pr` → `docs/BLOCKERS_AND_UNBLOCK_PLAN_2026-09-28.md`.

## How this inventory was built

Sources checked:

- open issues (none) and all 10 open pull requests;
- CI on `main`, for push and scheduled runs (GUI parity, Semgrep, maintenance, pip-audit, CodeQL, secret scan: all green on their latest runs);
- per-PR check results from the thehub federation completion-gate artifact (run `36326861596`);
- `docs/unfinished_implementation_ledger.v1.json`, reconciled against PR history;
- `docs/ROAD_TO_100.md` and `AUDIT.md`;
- thehub `docs/FEDERATION_MAX_AUDIT_2026-09-24.md`;
- the corpus files `data/master/master_cases.jsonl` and `data/candidates/candidate_cases.jsonl`;
- the branch list and branch protection.

## Summary

Each blocker is counted once, under its primary type.

| Type | Count |
|---|---:|
| DATA (operator runs) | 3 |
| IMPL | 3 |
| PR | 1 group (10 PRs) |
| STALE | 1 |
| **Total** | **8** |

## Blocker inventory

| ID | Blocker | Type | Evidence | Owner | Unblock step | Exit criterion |
|---|---|---|---|---|---|---|
| OV-01 | No recurring, governed source discovery or candidate intake | DATA (operator run) | Ledger OVN-004 (blocker `live_source_access`). The master corpus has held 470 cases since at least 2026-08-24; `data/candidates/candidate_cases.jsonl` holds 1 pending candidate. `docs/ROAD_TO_100.md` step 3. | Operator | Run the first governed intake cycle against the registered sources, recording source accounting | A reproducible run routes real candidates without modifying the master |
| OV-02 | No reviewed promotion stream | DATA (operator) | Ledger OVN-005: waiting on candidate review | Reviewer | Promote reviewed candidates one at a time, with validation and lineage receipts | Promotions recorded with receipts |
| OV-03 | Coordinate precision needs a backfill pass | DATA | Ledger OVN-006. 469 of 470 master cases carry coordinates; `location_confidence` is 0.4 for 25 cases, 0.5 for 18 and 0.6 for 9 | Agent/analyst | Resolve each case, or mark it explicitly unresolvable with source, method, precision and review state | No low-confidence case lacks a method or review state |
| OV-04 | The grid-cell schema rejects the canonical grid | IMPL | thehub MAX audit F10: `schemas/pr_grid_cell.schema.json:10` uses the pattern `^R\d{3}_C\d{3}$`, which rejects 54,000 of 98,304 canonical grid rows (IDs are unpadded, e.g. `R0_C0`). Dormant: no ovnis code references the schema. | Agent | Align the pattern with the hub's, or delete the dormant copy | The schema accepts the canonical grid |
| OV-05 | Toolchain diverges from the fleet (uv) | IMPL | `AUDIT.md`: `requirements.lock` is used instead of `uv.lock`. Dependabot requirement-floor bumps fail the `lock` check (#149). | Agent | Migrate to uv, or regenerate `requirements.lock` for each dependency bump | Dependency PRs pass the lock check |
| OV-06 | Case workflow routing and backend modules are missing | IMPL | `AUDIT.md` (corrected 2026-09-23): a single `Dashboard.jsx` page; the CandidateReview → CaseDetail routing layer is missing; case-management and spatial API modules are missing (`/municipios/case_density` exists and is tested) | Agent | Add page routing and domain API modules with tests | Case workflow reachable end to end |
| OV-07 | Open PRs | PR | See the next table | Agent + maintainer | Per-PR actions below | No red PRs |
| OV-08 | Stale ledger entries | STALE | See the reconciliation below: OVN-001, 002 and 003 are resolved | Agent/maintainer | New ledger version (X-07) | Ledger matches `main` |

### Open pull requests (OV-07)

| PR | State | Action |
|---|---|---|
| #160 Cell_Set uncertainty contract | Conflicts with `main` since the post-audit v0.2 series, which already carries the contract in `federation/spatial/registry_version.json` | Confirm v0.2 covers it, then close as superseded (X-05) |
| #155 actions minor/patch group | RED: Federation template drift | Land the bump via thehub `federation-templates`, re-render, close this PR |
| #152 eslint 10 | RED: GUI Reachability E2E, frontend | Migrate, or ignore the major (X-02) |
| #149 uvicorn ≥ 0.53 | RED: lock | Regenerate `requirements.lock` (OV-05) |
| #154 react-resizable-panels 4 (major), #153 vitest 5 (major) | Green | Review the major-version API changes; update the branch and merge |
| #151 npm group, #150 httpx, #148 fastapi, #147 python group | Green | Update the branch and merge |

## Unblock plan

### P1 — executable now
1. **OV-07:** merge the green PRs; route #155 through the templates; regenerate the lock for #149.
2. **OV-04:** fix or delete the grid schema.
3. **OV-05:** decide whether to migrate to uv.

### P2 — operator inputs
1. **OV-01:** first governed intake cycle.
2. **OV-02:** reviewed promotions.
3. **OV-03:** coordinate adjudication.

### P3 — maintainer decisions
1. Branch protection on `main` (X-03).
2. Decide on the eslint 10 major.

### P4 — longer horizon
1. **OV-06:** routing and domain API modules.

## Ledger reconciliation (`docs/unfinished_implementation_ledger.v1.json`, dated 2026-08-04)

| Ledger ID | Ledger state | State on 2026-09-28 |
|---|---|---|
| OVN-001 | open_pr (PR-70) | Resolved: #70 merged 2026-08-08 |
| OVN-002 | open_pr (PR-68) | Resolved: #68 closed unmerged 2026-08-27; superseded by the isolated-clone runtime |
| OVN-003 | stale_open_pr (PR-67) | Resolved: #67 closed; the real parity gate landed in #81 |
| OVN-004 | operator_run | Still open → OV-01 |
| OVN-005 | ongoing_data | Still open → OV-02 |
| OVN-006 | data_enrichment | Still open → OV-03 |

## Hygiene
- 19 branches on origin, including three `lockstep-canary-*` branches whose canary PRs are closed. Prune them if they are no longer needed as evidence.

## Federation-wide blockers that affect this repo
- X-01: completion gate.
- X-02: dependabot backlog and template drift.
- X-03: `main` is unprotected.
- X-05: the Cell_Set PR set, now superseded by v0.2 on `main`.
- X-07: stale ledgers.
- X-10: `main` lint is red since the v0.2 series; this PR carries the fix.

See the thehub document for details.

## Not verifiable with the access used for this audit
- Code-scanning and Dependabot security-alert inventories.
- Actions secrets.
- Live source access for intake.
