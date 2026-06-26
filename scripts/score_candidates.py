#!/usr/bin/env python3
"""Preliminary OVNIS candidate scoring.

This script assigns separable scores. It does not promote cases.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

EVIDENCE_BASE = {"T1": 0.95, "T2": 0.80, "T3": 0.60, "T4": 0.35}
SOURCE_DEFAULT = {"official": 0.95, "technical": 0.90, "news": 0.65, "ufo_archive": 0.60, "social": 0.25, "placeholder": 0.10}


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    evidence = EVIDENCE_BASE.get(row.get("evidence_tier"), 0.0)
    source_family = str(row.get("source_family") or "").lower()
    source = SOURCE_DEFAULT.get(source_family, 0.50)
    location = row.get("location_confidence")
    chronology = row.get("chronology_confidence")
    dedupe = row.get("dedupe_confidence")

    location_score = float(location) if isinstance(location, (int, float)) else (0.75 if row.get("latitude") and row.get("longitude") else 0.35)
    chronology_score = float(chronology) if isinstance(chronology, (int, float)) else (0.80 if len(str(row.get("date_local", ""))) == 10 else 0.45)
    dedupe_score = float(dedupe) if isinstance(dedupe, (int, float)) else (0.30 if row.get("dedupe_status") == "not_checked" else 0.70)

    final = round((evidence * 0.40) + (source * 0.20) + (location_score * 0.15) + (chronology_score * 0.15) + (dedupe_score * 0.10), 3)

    out = dict(row)
    out["source_reliability"] = round(source, 3)
    out["location_confidence"] = round(location_score, 3)
    out["chronology_confidence"] = round(chronology_score, 3)
    out["dedupe_confidence"] = round(dedupe_score, 3)
    out["case_confidence"] = final
    return out


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score OVNIS candidate rows without promoting them")
    parser.add_argument("--input", default="data/candidates/candidate_cases.jsonl")
    parser.add_argument("--output", default="reports/candidate_scoring.csv")
    args = parser.parse_args()

    rows = [score_row(row) for row in iter_jsonl(Path(args.input))]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, output)
    print(f"Wrote {len(rows)} scored candidate rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
