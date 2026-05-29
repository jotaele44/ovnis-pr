# PRUFON GitHub Control Plane

## Operating position

GitHub is the control plane for PRUFON, not the only operational database.

The repository should govern code, schema, validation, review gates, candidate intake, deduplication, evidence scoring, and release snapshots. The live analytical database can be SQLite, DuckDB, or later PostgreSQL/PostGIS, but every promoted case must remain reproducible from versioned files, manifests, and validation reports.

## Active vector

`DESIGN_PRUFON_GITHUB_CONTROL_PLANE`

## Control-plane objectives

| Objective | Implementation |
|---|---|
| Preserve provenance | Require source URL, source label, source language, retrieval timestamp, and optional content hash. |
| Prevent database contamination | Web intake writes only to candidate ledgers, never directly to the master ledger. |
| Enforce promotion discipline | Master case additions occur through reviewed pull requests or explicitly logged commits. |
| Maintain chronology | Validator blocks malformed dates and can warn on chronology drift. |
| Detect duplicates | Dedupe stage compares case date, location, source lineage, description, and evidence profile. |
| Separate signal from noise | Candidate, promoted, duplicate, rejected, and social-monitoring ledgers remain separate. |
| Support release snapshots | Every release exports CSV/JSONL/Parquet/GeoJSON where available plus checksums and manifests. |

## Repository layers

```text
PRUFON/
  data/
    candidates/          # quarantined web/social/manual intake
    master/              # promoted case ledger snapshots
    reference/           # source registry and controlled vocabularies
    schemas/             # JSON Schema contracts
  docs/                  # operating doctrine and promotion/release rules
  scripts/               # validation, dedupe, scoring, export utilities
  reports/               # generated validation/dedupe/release reports
  .github/
    workflows/           # CI, scheduled intake, release validation
```

## Intake doctrine

Automated ingestion is allowed only into the candidate layer.

```text
web/source discovery
  -> raw source metadata
  -> candidate extraction
  -> schema validation
  -> dedupe against master
  -> evidence scoring
  -> review queue
  -> promotion commit/PR
  -> release snapshot
```

## Promotion doctrine

A case can be promoted only when it has:

1. A stable `case_id`.
2. A normalized date field.
3. A non-generic location.
4. A source URL or archival pointer.
5. An evidence tier.
6. A dedupe status.
7. A contradiction/gap note, even if empty.
8. A reviewer action: `promote`, `merge`, `reject`, or `monitor`.

## Ledger separation

| Ledger | Purpose | Automation allowed? |
|---|---|---:|
| `candidate_cases` | Raw or semi-normalized discovered cases | Yes |
| `master_cases` | Reviewed and promoted cases | No direct automation |
| `already_listed` | Duplicates or known case matches | Yes, but review required |
| `updates_new_evidence` | New data attached to existing cases | Semi-automatic |
| `echoes_noise` | Social chatter, reposts, weak leads | Yes |

## Evidence tiers

| Tier | Description |
|---|---|
| T1 | Technical, official, radar, sensor, military/government document, instrumented evidence. |
| T2 | Operational witness or institutionally credible observation: pilot, crew, police, military, agency, maritime operator. |
| T3 | Eyewitness case with multiple observers, interview record, named witness, or coherent documentation. |
| T4 | Secondary source, repost, summary, weak provenance, social-media echo, or unverified archive reference. |

## Confidence model

Confidence must not be collapsed into a single opaque number. Store separable components:

| Field | Meaning |
|---|---|
| `evidence_tier` | Type and strength of evidence. |
| `source_reliability` | Reliability of source family. |
| `dedupe_confidence` | Confidence that this is new or matched to an existing case. |
| `location_confidence` | Precision and reliability of geolocation. |
| `chronology_confidence` | Precision and reliability of date/time. |
| `case_confidence` | Final derived confidence, if used. |

## Automation boundaries

Allowed:

- Search source registry.
- Extract candidate rows.
- Normalize dates and locations.
- Generate translations.
- Score evidence preliminarily.
- Generate dedupe reports.
- Open review issues or output review CSVs.

Not allowed without human review:

- Promote to master ledger.
- Overwrite existing case descriptions.
- Delete cases.
- Merge uncertain duplicates.
- Treat social chatter as confirmed evidence.

## Release doctrine

Release snapshots should include:

```text
prufon_cases_master.csv
prufon_cases_master.jsonl
prufon_candidate_cases.csv
already_listed.csv
updates_new_evidence.csv
echoes_noise.csv
source_manifest.json
validation_report.md
dedupe_report.md
checksums.sha256
```

## Vector status

This document defines the initial control-plane doctrine. Implementation files in this patch add schemas, validation scaffolding, workflow stubs, and release rules.
