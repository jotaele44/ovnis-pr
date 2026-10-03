# OVNIS research ledgers

OVNIS owns the Federation's research record for its case corpus. That covers topics, findings, hypotheses
and their falsification checks, contradictions, manifestation adjudications, the research queue, media
episodes and per-case reports. TheHub is the only product GUI (ADR 0001), so OVNIS records, validates and
exports these records, and TheHub renders them.

**No research content exists yet.** The curated ledgers are committed empty. They are filled only as real
research is recorded. Nothing is generated into them, and nothing is promoted from search output.

## Files

| Path | Written by | Holds |
|---|---|---|
| `data/research/topics.jsonl` | curators | research topics (`TOPIC-…`) |
| `data/research/findings.jsonl` | curators | findings (`FIND-…`) |
| `data/research/hypotheses.jsonl` | curators | hypotheses with the nine falsification checks (`HYP-…`) |
| `data/research/contradictions.jsonl` | curators | contradictions, with both claims kept verbatim (`CONTRA-…`) |
| `data/research/manifestation_adjudications.jsonl` | curators | reviewed decisions on case pairs (`ADJ-…`) |
| `data/research/research_queue.jsonl` | curators | open questions and retrieval tasks (`RQ-…`) |
| `data/research/media_episodes.jsonl` | curators | broadcast episodes and their primary sources (`EP-…`) |
| `data/research/manifestation_candidates.jsonl` | `scripts/dedupe_candidates.py --master-pairs` | computed CANDIDATE case pairs (`ADJ-C-…`) |

Each kind has a JSON Schema under `schemas/research/`. `case_report.v1.schema.json` describes the
generated per-case report.

## Rules

`scripts/validate_research_ledgers.py` enforces these rules in CI:

- Every row matches its schema. Every case, source-registry, topic, finding, hypothesis and adjudication id
  a row names resolves to a real record.
- **A finding is not an established fact.** `ACCEPTED` means a reviewer accepted it as supported by its
  cited sources. It requires at least one `source_refs` entry and a `review` block. An `INTERPRETIVE`
  finding states its `interpretation_basis`.
- A hypothesis is `SUPPORTED` only when all nine falsification checks were run and none `FAILED`. The
  checks are identity errors, duplicate manifestations, ordinary explanations, background prevalence,
  missing data, source dependence, temporal mismatch, geometry uncertainty and contradictions.
- A `SUPERSEDED` record names the record that supersedes it.
- Curated records carry `origin: CURATED`. A record is never promoted from search output.
- **Similarity never decides identity.** Computed pairs are always `COMPUTED` and `CANDIDATE`. Only a
  curator's entry in `manifestation_adjudications.jsonl`, with `reviewed_by` and a `rationale`, can record
  `SAME_EVENT`, `DISTINCT` or `UNRESOLVABLE`. No adjudication merges or edits a case.
- **Records are retained.** On a pull request, `--base <sha>` fails if any record present at the base
  has been deleted. A record is retired by status (`REJECTED`, `SUPERSEDED`, `DROPPED`), never removed.

## Duplicate-manifestation candidates

`python3 scripts/dedupe_candidates.py --master-pairs` pairs master cases when two conditions both hold:

1. Their recorded dates agree at the coarser of the two precisions. For example, `1972` agrees with
   `1972-10-13`.
2. They share a place: the same recorded municipality or, when either case has none, near-identical
   location text (ratio ≥ 0.85). Two different recorded municipalities never pair.

Narrative similarity and a shared source URL are recorded as `signals` for the reviewer. They rank the
queue; they decide nothing.

The output is sorted and carries no timestamps. CI runs `--check` and fails when the committed file is
stale. At the time of writing the corpus yields 38 pairs.

## Case reports

`python3 scripts/generate_case_report.py --case <id>` (or `--all`) writes a JSON and a Markdown report per
case to `reports/cases/`. That directory is generated and not committed. Each report contains:

- the case **as recorded**: a year-only date stays a year, and an absent field is reported as not recorded;
- the narrative and citation;
- the federation evidence ids of the case's exported rows;
- every research record that names the case;
- an `unresolved` list: open contradictions, open hypotheses, open queue items, unreviewed duplicate
  candidates, and recorded gaps such as a missing municipality or a coarse date;
- a reproducibility receipt shaped after TheHub's `analytical_run_receipt.v1`. It holds `run_id`,
  `snapshot_id` (the master ledger's sha256), `input_sha256` for every ledger read, the generator and its
  commit, `report_sha256` and `created_at`. The same inputs always give the same `report_sha256`.

When `source_url` holds a publication name instead of a link, the report shows it as a `locator` and
never as a URL.

## Federation export

`scripts/federation_export.py` adds the research records to the existing `entities`, `relationships` and
`sources` streams. Each record becomes an entity row whose `entity_type` is its kind, with the record in
`attributes`. No new stream and no change to the frozen stream schemas is involved.

| Row | `evidence_state` |
|---|---|
| finding | `data_stage: FINDING`, its declared class |
| hypothesis | `INTERPRETATION`, `INTERPRETIVE` |
| other curated records | `CANONICAL`, `CURATED` |
| computed pair | `COMPUTATION`, `COMPUTED` |
| case report | `REPORT`, `COMPUTED` |

Links are exported as relationships:

- `about_case`, `in_topic`, `tests` (hypothesis → finding), `mentions`;
- `cites` (finding → the case's source document, with the locator);
- `candidate_duplicate_of`, which carries `match_basis: co_occurrence`. The Hub treats that basis as weak,
  so the edge stays CANDIDATE.

A curated `SAME_EVENT` decision replaces its computed pair with a `same_event_as` edge. A link to an
unknown case is dropped rather than pointed at an invented entity.

The research ledger and each generator appear as their own `sources` rows, so every research row names
where it came from.

## Open lead: `gap_note`

92 master cases carry a `gap_note`, and every value names agencies. Examples: "U.S. Navy" (37),
"NARA (CAB/CAA records 1957) + USAF/DoD", "PR Emergency Management Agency (PREMA); DoD via FOIA".

In 24 of the 92, the agency also appears in the case narrative. A plausible reading is "an agency that may
hold records on this case", but no schema description, import mapping or document declares that meaning.
Research-queue items are therefore **not** derived from it. A curator must confirm the field's meaning
first; until then the queue stays empty.
