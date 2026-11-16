#!/usr/bin/env python3
"""Measure how complete the OVNIS corpus is (report only).

Counts what the ledgers actually contain: how many master cases carry each
provenance field, how coordinates and confidence are distributed, how many real
candidates are staged, and how many rows each research ledger holds. It prints
JSON and never edits a ledger.

The numbers are the baseline that ``docs/unfinished_implementation_ledger.v2.json``
states its exit criteria against. A count here is a measurement of field
presence, not a judgement that the value is correct.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from validate_case_ledgers import _present, iter_jsonl

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "master" / "master_cases.jsonl"
CANDIDATES = ROOT / "data" / "candidates" / "candidate_cases.jsonl"
RESEARCH_DIR = ROOT / "data" / "research"
ADJUDICATION = ROOT / "data" / "reference" / "source_reference_adjudication_v1.csv"

# Fields the operating contract expects a promoted case to retain.
PROVENANCE_FIELDS = (
    "source_url",
    "source_family",
    "source_citation",
    "source_hash",
    "retrieved_at",
    "municipality",
    "nearest_feature",
    "time_local",
)
# A source_family of "none" is a filled-in placeholder, not a source family.
EMPTY_SOURCE_FAMILIES = {"none", "unknown"}
# No case carries these yet; they are counted so the first one that does shows up.
COORDINATE_PROVENANCE_FIELDS = (
    "coordinate_source",
    "coordinate_method",
    "coordinate_precision",
    "coordinate_review_state",
)
PLACEHOLDER_CANDIDATE_IDS = {"CAND-0000"}


def _counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter("null" if row.get(key) is None else str(row[key]) for row in rows)
    return dict(sorted(counter.items()))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def master_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    present = {field: sum(1 for row in rows if _present(row, field)) for field in PROVENANCE_FIELDS}
    present["source_family"] = sum(
        1
        for row in rows
        if _present(row, "source_family")
        and str(row["source_family"]).strip().lower() not in EMPTY_SOURCE_FAMILIES
    )
    return {
        "rows": len(rows),
        "created_month_counts": _counts(
            [{"m": str(row.get("created_at") or "")[:7] or None} for row in rows], "m"
        ),
        "provenance_field_present": present,
        "coordinate_pair_count": sum(
            1 for row in rows if _is_number(row.get("latitude")) and _is_number(row.get("longitude"))
        ),
        "coordinate_provenance_row_count": sum(
            1 for row in rows if any(_present(row, field) for field in COORDINATE_PROVENANCE_FIELDS)
        ),
        "location_confidence_counts": _counts(rows, "location_confidence"),
        "evidence_tier_counts": _counts(rows, "evidence_tier"),
        "case_confidence_counts": _counts(rows, "case_confidence"),
        "dedupe_status_counts": _counts(rows, "dedupe_status"),
        "review_action_counts": _counts(rows, "review_action"),
    }


def candidate_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    placeholders = sum(1 for row in rows if row.get("candidate_id") in PLACEHOLDER_CANDIDATE_IDS)
    return {"rows": len(rows), "placeholder_rows": placeholders, "real_rows": len(rows) - placeholders}


def research_metrics(research_dir: Path) -> dict[str, int]:
    return {path.stem: len(iter_jsonl(path)) for path in sorted(research_dir.glob("*.jsonl"))}


def adjudication_metrics(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        counter = Counter(row.get("adjudication_state") or "null" for row in csv.DictReader(handle))
    return dict(sorted(counter.items()))


def build_report(
    master: Path = MASTER,
    candidates: Path = CANDIDATES,
    research_dir: Path = RESEARCH_DIR,
    adjudication: Path = ADJUDICATION,
) -> dict[str, Any]:
    return {
        "schema_version": "ovnis_corpus_quality_report_v1",
        "master": master_metrics(iter_jsonl(master)),
        "candidates": candidate_metrics(iter_jsonl(candidates)),
        "research_ledger_rows": research_metrics(research_dir),
        "source_reference_adjudication_states": adjudication_metrics(adjudication),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--research-dir", type=Path, default=RESEARCH_DIR)
    parser.add_argument("--adjudication", type=Path, default=ADJUDICATION)
    parser.add_argument("--out", type=Path, help="Also write the report to this file.")
    args = parser.parse_args(argv)

    report = build_report(args.master, args.candidates, args.research_dir, args.adjudication)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
