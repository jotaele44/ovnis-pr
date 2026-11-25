# Road to 100 — normalized federation score

**Audit date:** 2026-11-14 · **`main` at audit:** `abf48ed`  
**Scoring model:** code completeness 20%; main-branch availability 15%; CI enforcement 15%; data materialization 15%; operator verification 15%; GUI completeness 10%; federation readiness 10%.

## Current normalized score: 78.00 / 100

Dimension scores are audit estimates. The counts under "Measured state" are not estimates: they come
from `python3 scripts/corpus_quality_report.py`.

| Dimension | Weight | Score | Weighted | Change since 2026-08-04 |
|---|---:|---:|---:|---|
| Code completeness | 20 | 90 | 18.00 | unchanged |
| Main-branch availability | 15 | 95 | 14.25 | +7: the isolated-clone runtime landed and every workflow is green on `main` |
| CI enforcement | 15 | 85 | 12.75 | +7: coverage floor, GUI parity, docs-sync and lockstep now gate; mypy is still report-only |
| Data materialization | 15 | 60 | 9.00 | −15: the earlier score counted cases, not the provenance fields each case carries |
| Operator verification | 15 | 50 | 7.50 | −15: no intake cycle, promotion or adjudication has run |
| GUI completeness | 10 | 80 | 8.00 | +5: error states, tests and an accessibility gate; the surface stays diagnostic-only |
| Federation readiness | 10 | 85 | 8.50 | unchanged |

The total fell from 79.90 although engineering improved, because the two data dimensions are now
scored against what the ledgers contain.

## Measured state

| Measure | Value |
|---|---:|
| Master cases | 470, all created 2026-06 |
| Real staged candidates | 0 (one placeholder row) |
| Cases with a source family | 120 of 470 |
| Cases with a source citation | 4 of 470 |
| Cases with a source hash or retrieval time | 0 of 470 |
| Cases with a municipality | 93 of 470 |
| Cases with a coordinate pair | 469 of 470 |
| Cases with coordinate provenance | 0 of 470 |
| Cases at `location_confidence` 0.6 or lower | 52 |
| Manifestation candidates adjudicated | 0 of 38 |
| Research ledgers with no rows | 7 of 8 |
| Source references still `DISCOVERY_ONLY` | 190 of 244 |
| Open pull requests | 16 |

## State reconciliation

- Ledger items OVN-001, OVN-002 and OVN-003 are resolved (#70 merged; #68 and #67 closed, superseded).
- Since 2026-09-01 `main` gained 55 commits. About 24 freeze, adjudicate or bind a receipt. None adds or
  enriches a case.
- The receipts certify a corpus that has not changed since June. Most of its records lack the
  provenance fields the operating contract in `README.md` requires.
- The first real intake (five NARA FAA reports, #177) has been a draft since 2026-10-11.

## Priority exit sequence

Work is ordered by how much it moves the measured state. Do not add a certification layer until the
corpus it certifies has changed.

1. **Clear the backlog (OVN-009).** Merge or close the 16 open pull requests with a recorded
   disposition, and protect `main`.
2. **Make intake real (OVN-004, OVN-005).** Land #177 as the first governed intake cycle, promote
   each reviewed candidate individually, then remove the placeholder candidate row.
3. **Enrich the existing 470 (OVN-006, OVN-007).** Bind cases to registered sources where the
   reference adjudicates unambiguously. Derive municipality from coordinates and label it as derived.
   Record source, method, precision and review state for every coordinate pair.
4. **Fill the research ledgers (OVN-008).** Adjudicate the 38 manifestation candidates and seed the
   research queue from the gaps step 3 exposes.
5. **Engineering ratchets.** Make mypy gating, raise the coverage floor, and add Python 3.13 to the
   validation matrix. Add no dashboard pages or native-wrapper work while the surface is
   diagnostic-only (thehub-pr ADR 0001).

Issue one receipt per completed step, and only when the measured state has changed.

## Machine-readable authority

See `docs/unfinished_implementation_ledger.v2.json`, which supersedes
`docs/unfinished_implementation_ledger.v1.json` (kept as the 2026-08-04 record). Each open item states
its exit criterion against the measured state above. A production corpus is not equivalent to a
continuously maintained intake system.
