#!/usr/bin/env python3
"""Audit OVNIS master-case coordinates for PR Grid V2 migration eligibility.

Coordinate presence is discovery only. EXACT_SOURCE_POINT eligibility requires an
explicit VERIFIED_SOURCE_COORDINATE evidence marker; confidence scores, source
tiers, location names, or numeric lat/lon do not substitute for provenance.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO_ROOT / "data/master/master_cases.jsonl"
EVIDENCE_STATE = "VERIFIED_SOURCE_COORDINATE"
PROVENANCE_FIELDS = (
    "grid_v2_coordinate_evidence_state",
    "coordinate_evidence_state",
    "coordinate_source",
    "coordinate_method",
    "coordinate_precision",
    "geocode_source",
    "geocode_method",
)


class CoordinateEvidenceAuditError(ValueError):
    pass


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CoordinateEvidenceAuditError(
                f"invalid JSON at {path}:{line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise CoordinateEvidenceAuditError(
                f"row {line_number} must be a JSON object"
            )
        rows.append(row)
    return rows


def _numeric_pair(row: dict[str, Any]) -> bool:
    lat = row.get("latitude")
    lon = row.get("longitude")
    return (
        isinstance(lat, (int, float))
        and not isinstance(lat, bool)
        and isinstance(lon, (int, float))
        and not isinstance(lon, bool)
    )


def _marker(row: dict[str, Any]) -> object:
    if "grid_v2_coordinate_evidence_state" in row:
        return row["grid_v2_coordinate_evidence_state"]
    attrs = row.get("attributes")
    if isinstance(attrs, dict):
        return attrs.get("grid_v2_coordinate_evidence_state")
    return None


def audit(path: Path) -> dict[str, Any]:
    rows = _load(path)
    masters = [row for row in rows if row.get("record_type") == "master"]
    numeric = [row for row in masters if _numeric_pair(row)]
    marked = [row for row in masters if _marker(row) == EVIDENCE_STATE]
    admissible = [row for row in marked if _numeric_pair(row)]

    provenance_rows = 0
    for row in masters:
        attrs = row.get("attributes")
        has_top = any(field in row for field in PROVENANCE_FIELDS)
        has_attrs = isinstance(attrs, dict) and any(
            field in attrs for field in PROVENANCE_FIELDS
        )
        if has_top or has_attrs:
            provenance_rows += 1

    confidence = Counter(str(row.get("location_confidence")) for row in numeric)

    migration_state = (
        "CANDIDATE_EXACT_SOURCE_POINT_DENOMINATOR_AVAILABLE"
        if admissible
        else "BLOCKED_NO_VERIFIED_SOURCE_COORDINATE_DENOMINATOR"
    )
    return {
        "contract": "ovnis-pr-grid-v2-coordinate-evidence-audit/1.0",
        "Source_Path": str(path.relative_to(REPO_ROOT)),
        "Total_Row_Count": len(rows),
        "Master_Row_Count": len(masters),
        "Numeric_Coordinate_Pair_Count": len(numeric),
        "Missing_Or_NonNumeric_Coordinate_Pair_Count": len(masters) - len(numeric),
        "Verified_Source_Coordinate_Marker_Count": len(marked),
        "Exact_Source_Point_Admissible_Count": len(admissible),
        "Coordinate_Provenance_Field_Row_Count": provenance_rows,
        "Location_Confidence_Counts": dict(sorted(confidence.items())),
        "Required_Evidence_State": EVIDENCE_STATE,
        "Coordinate_Presence_Is_Exact_Evidence": False,
        "Location_Confidence_Is_Exact_Evidence": False,
        "Evidence_Tier_Is_Exact_Coordinate_Evidence": False,
        "Migration_Input_Class": "EXACT_SOURCE_POINT",
        "Migration_State": migration_state,
        "Promotion_State": "CANDIDATE_NOT_CANONICAL",
        "Identity_Default": "CANDIDATE_NOT_IDENTITY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = audit(args.ledger)
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
