# PRUFON — Puerto Rico Historical Case Corpus Producer (PRII federation)

`PRUFON` is the historical case-corpus producer for Puerto Rico-centered anomalous-event research in the Puerto Rico Integrated Intelligence (PRII) federation.

Its federation alias is `prufon-pr`. It should preserve case provenance, chronology, location references, witness/source tiers, document lineage, and review state for downstream analysis in [`thehub-pr`](https://github.com/jotaele44/thehub-pr) and analytical consumers.

## Federation role

| Field | Value |
|---|---|
| Repository | `jotaele44/PRUFON` |
| Federation alias | `prufon-pr` |
| Parent hub | [`thehub-pr`](https://github.com/jotaele44/thehub-pr) |
| Primary function | Historical case corpus and review pipeline |
| Jurisdiction focus | Puerto Rico |

## Operating doctrine

| Rule | Requirement |
|---|---|
| Provenance first | Every promoted case should retain source, date, location, and review trail where available |
| No silent substitution | Unknown values stay unknown rather than inferred as fact |
| Tiered evidence | Separate technical records, operational records, eyewitness material, and secondary sources |
| Review queue | Ambiguous cases remain staged until enough metadata exists for promotion |
| Federation boundary | PRUFON exports case records; Hub performs cross-producer correlation |

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

PRUFON should emit canonical Hub-compatible records:

```text
sources.jsonl
entities.jsonl
relationships.jsonl
observations.jsonl
manifest.json
```

Do not treat exported cases as conclusions. Treat them as structured historical records available for correlation and review.
