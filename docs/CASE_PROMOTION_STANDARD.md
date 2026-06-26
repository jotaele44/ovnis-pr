# OVNIS Case Promotion Standard

## Purpose

This standard controls how a candidate case becomes a promoted OVNIS case.

The master ledger must remain chronologically stable, deduplicated, source-traceable, and evidence-bounded.

## Promotion states

| State | Meaning |
|---|---|
| `candidate` | Newly discovered or manually entered case; not yet reviewed. |
| `needs_dedupe` | Candidate requires match check against the master ledger. |
| `duplicate` | Candidate matches an existing case. |
| `update_existing` | Candidate adds new evidence or metadata to an existing case. |
| `promote_ready` | Candidate passes minimum requirements. |
| `promoted` | Candidate has entered the master ledger. |
| `rejected` | Candidate does not meet minimum criteria. |
| `monitor` | Weak or noisy signal retained for future cross-reference. |

## Minimum promotion criteria

A row must satisfy at least one of the following:

| Criterion | Description |
|---|---|
| Evidence | Photo, video, radar, official document, sensor record, archival clipping, or other documentary evidence. |
| Credible/corroborated witness | Pilot, crew, police, military, maritime operator, agency witness, or two or more observers. |
| Extensive documentation | News series, FOIA record, book, interview, archive dossier, or repeated independent references. |

## Required fields

| Field | Requirement |
|---|---|
| `case_id` | Required for promoted cases. Candidate rows may use `candidate_id`. |
| `date_local` | Required. Use ISO `YYYY-MM-DD` when exact date is known. |
| `time_local` | Optional but must use `HH:MM` 24-hour format when known. |
| `location_name` | Required. Must be more specific than only Puerto Rico/PR. |
| `municipality` | Required when known. |
| `latitude` / `longitude` | Optional for weak cases; required for GIS-ready promotion. |
| `description` | Required factual summary. |
| `source_url` | Required unless source is offline-only; then use `source_citation`. |
| `evidence_tier` | Required: `T1`, `T2`, `T3`, or `T4`. |
| `dedupe_status` | Required before promotion. |
| `review_action` | Required: `promote`, `merge`, `reject`, or `monitor`. |

## Description standard

Descriptions should be concise and factual. Include:

- Object or phenomenon type.
- Color, shape, trajectory, altitude/depth, and duration when available.
- Witness class and count when available.
- Evidence type.
- Agency or institutional involvement when available.
- Secondary references when relevant.
- Translation note if source is Spanish and summary is translated.

Avoid:

- Unsupported causal claims.
- Speculation presented as fact.
- Repeated folklore without source lineage.
- Dramatic wording.

## Dedupe requirement

Every candidate must be compared against the master ledger using:

| Signal | Weight |
|---|---:|
| Date proximity | High |
| Location proximity | High |
| Source lineage | High |
| Witness overlap | High |
| Description similarity | Medium |
| Time of day | Medium |
| Object behavior | Medium |

## Promotion output

Promoted cases must be written to the master ledger and reflected in the next release snapshot.

Rejected and duplicate candidates must remain traceable through `already_listed`, `rejected`, or `monitor` outputs.
