# OVNIS — Puerto Rico Historical Case Corpus Producer (PRII federation)

`OVNIS` is the historical case-corpus producer for Puerto Rico-centered anomalous-event research in the Puerto Rico Integrated Intelligence (PRII) federation.

Its federation alias is `ovnis-pr`. It should preserve case provenance, chronology, location references, witness/source tiers, document lineage, and review state for downstream analysis in [`thehub-pr`](https://github.com/jotaele44/thehub-pr) and analytical consumers.

> **Diagnostic-only surface (ADR 0001, Phase 2).** This repo's dashboard is a
> development and diagnostic tool for this producer only. The supported product
> surface for the PRII federation is the hub app
> (`thehub-pr/server/frontend`), which renders this producer's data alongside
> the other engines. See `thehub-pr/docs/adr/0001-federated-engines-single-hub.md`.

## Federation role

| Field | Value |
|---|---|
| Repository | `jotaele44/ovnis-pr` |
| Federation alias | `ovnis-pr` |
| Parent hub | [`thehub-pr`](https://github.com/jotaele44/thehub-pr) |
| Primary function | Historical case corpus and review pipeline |
| Jurisdiction focus | Puerto Rico |

## Desktop app

Double-click launchers at the repo root start the local desktop app (first run
installs dependencies, later runs work offline):

- `PRII-OVNIS.command` (macOS) / `PRII-OVNIS.app`
- `PRII-OVNIS.bat` (Windows)
- `PRII-OVNIS.sh` (Linux)

See [`desktop/README.md`](desktop/README.md) for details.

## Setup / Development

Requires **Python 3.10+** (CI's `validate` job tests 3.10–3.12; the `OVNIS CI`
job runs on 3.12). This repo is a flat-layout application — modules run in place,
there is no package install — so setup is just the runtime/test dependencies.

```bash
git clone https://github.com/jotaele44/ovnis-pr.git
cd ovnis-pr
python3 -m venv .venv
source .venv/bin/activate

# requirements.txt pins the shared prii-* packages to an immutable TheHub git
# SHA, fetched straight from GitHub — no sibling ../thehub-pr checkout needed
# (CI asserts one is absent). CI also needs the backend deps to run the suite:
python -m pip install -r requirements.txt httpx -r server/backend/requirements.txt
```

> `requirements.txt` pins the shared federation packages (`prii-maintenance`,
> `prii-export-utils`) to an immutable git SHA in `thehub-pr`
> (`git+...@f2b8176...`), not a live local path. Picking up a change made in
> the hub requires bumping that pinned SHA here and regenerating
> `requirements.lock` — it does not propagate automatically.

Run the checks CI runs:

```bash
python3 scripts/validate_case_ledgers.py            # ledger integrity
python -m pytest -q                                 # unit tests
python3 scripts/federation_export.py --mode test    # canonical export smoke
```

## Operating doctrine

| Rule | Requirement |
|---|---|
| Provenance first | Every promoted case should retain source, date, location, and review trail where available |
| No silent substitution | Unknown values stay unknown rather than inferred as fact |
| Tiered evidence | Separate technical records, operational records, eyewitness material, and secondary sources |
| Review queue | Ambiguous cases remain staged until enough metadata exists for promotion |
| Federation boundary | OVNIS exports case records; Hub performs cross-producer correlation |

## Suggested repository layout

```text
data/             raw and normalized case material
reports/          generated summaries and review outputs
scripts/          import, validation, deduplication, and reporting tools
docs/             methodology, source policy, FOIA notes, and analyst runbooks
tests/            validation and regression tests
exports/          federation-ready export packages
```

## Minimum promotion fields

| Field | Purpose |
|---|---|
| `case_id` | Stable local identifier |
| `event_date` | Known or bounded date/time |
| `municipio` / `location` | Spatial anchor for Puerto Rico analysis |
| `source_tier` | Evidence tier classification |
| `source_ref` | Document, URL, archive, interview, or file reference |
| `summary` | Controlled, non-dramatized case summary |
| `confidence` | Review-grade confidence score |
| `review_status` | `draft`, `needs_review`, `promoted`, or equivalent |

## Federation export target

OVNIS should emit canonical Hub-compatible records:

```text
sources.jsonl
entities.jsonl
relationships.jsonl
observations.jsonl
manifest.json
```

Do not treat exported cases as conclusions. Treat them as structured historical records available for correlation and review.

<!-- PROJECT-OPERATING-CONTRACT:START -->
## Current development and certification contract

OVNIS is the Puerto Rico UAP/USO historical case-corpus producer and evidence-analysis system. Research completeness, case/source identity, provenance, chronology, spatial precision, contradictions, and source manifestations take priority over speculative interface growth.

**Evidence rules:** preserve atomic claims and their source/time/page context; record successful, zero-result, blocked, stale, and failed acquisition attempts; source taxonomy is not canonical identity; never merge cases from name/date/proximity/normalization/count equality alone. Preserve full candidate sets and unresolved ties. Spatial outputs must distinguish FULLY_WITHIN, PARTIAL, TOUCH_ONLY, OUTSIDE, NULL_EMPTY, and UNRESOLVED where applicable.

**Certification:** corpus, runtime, federation package, rendered desktop+iPhone, and native claims are separate gates. Historical or local PASS receipts do not prove current production state. Certify only a bounded declared universe with frozen inputs/hashes, explicit inclusion/exclusion, closed arithmetic, adjudicated duplicates/edges, validated IDs, positive/negative regressions, and zero material unresolved residue inside the claim.
<!-- PROJECT-OPERATING-CONTRACT:END -->
