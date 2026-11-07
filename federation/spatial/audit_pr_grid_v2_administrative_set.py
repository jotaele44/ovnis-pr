#!/usr/bin/env python3
"""Audit OVNIS municipality labels for PR Grid V2 ADMINISTRATIVE_SET eligibility.

This audit is intentionally identity-conservative. A textual municipality label,
case-folded name, normalized alias, location string, or coordinate proximity does
not establish canonical municipio identity. ADMINISTRATIVE_SET admission requires
an independently bound stable municipio identifier (currently a 5-digit PR GEOID)
or another explicit authoritative binding supplied in the source record.

The current master ledger therefore remains source-bounded: broad regional labels
are preserved as written and are not converted into municipality polygons.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO_ROOT / "data/master/master_cases.jsonl"
GEOID_FIELDS = (
    "municipality_geoid",
    "municipio_geoid",
    "county_geoid",
)
CONTRACT = "ovnis-pr-grid-v2-administrative-set-denominator/1.0"


class AdministrativeSetAuditError(ValueError):
    pass


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdministrativeSetAuditError(
                f"invalid JSON at {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise AdministrativeSetAuditError(
                f"row {line_number} must be a JSON object"
            )
        rows.append(value)
    return rows


def _raw_label(row: dict[str, Any]) -> str | None:
    value = row.get("municipality")
    if isinstance(value, str) and value.strip():
        return value
    value = row.get("municipio")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _stable_geoid(row: dict[str, Any]) -> str | None:
    for field in GEOID_FIELDS:
        value = row.get(field)
        if isinstance(value, str) and len(value) == 5 and value.isdigit() and value.startswith("72"):
            return value
    return None


def audit(path: Path) -> dict[str, Any]:
    rows = _load(path)
    masters = [row for row in rows if row.get("record_type") == "master"]
    labels = Counter()
    geoid_bound = []
    nonblank = 0

    for row in masters:
        label = _raw_label(row)
        if label is not None:
            nonblank += 1
            labels[label] += 1
        if _stable_geoid(row) is not None:
            geoid_bound.append(row)

    return {
        "contract": CONTRACT,
        "Source_Path": str(path.relative_to(REPO_ROOT)),
        "Total_Row_Count": len(rows),
        "Master_Row_Count": len(masters),
        "Nonblank_Municipality_Label_Row_Count": nonblank,
        "Blank_Municipality_Label_Row_Count": len(masters) - nonblank,
        "Unique_Nonblank_Municipality_Label_Count": len(labels),
        "Municipality_Label_Counts_RAW": dict(
            sorted(labels.items(), key=lambda item: (-item[1], item[0]))
        ),
        "Stable_Municipio_GEOID_Row_Count": len(geoid_bound),
        "Administrative_Set_Admissible_Count": len(geoid_bound),
        "Required_Stable_ID_Prefix": "72",
        "Text_Name_Match_Is_Identity": False,
        "Casefolded_Name_Match_Is_Identity": False,
        "Normalized_Alias_Is_Identity": False,
        "Location_Text_Is_Identity": False,
        "Coordinate_Proximity_Is_Identity": False,
        "Migration_Input_Class": "ADMINISTRATIVE_SET",
        "Required_Binding_Method": "ADMINISTRATIVE_SET",
        "Required_Uncertainty_Class": "ADMINISTRATIVE_ONLY",
        "Required_Geometry_Evidence_State": "VERIFIED_ADMINISTRATIVE_GEOMETRY",
        "Migration_State": (
            "CANDIDATE_ADMINISTRATIVE_SET_DENOMINATOR_AVAILABLE"
            if geoid_bound
            else "BLOCKED_NO_STABLE_MUNICIPIO_ID_DENOMINATOR"
        ),
        "Promotion_State": "CANDIDATE_NOT_CANONICAL",
        "Identity_Default": "CANDIDATE_NOT_IDENTITY",
        "Scope_Note": (
            "Raw municipality labels are preserved for discovery/source-bounded geography. "
            "No municipality polygon is assigned from name normalization, regional labels, "
            "location text, or unverified coordinates. A stable authoritative municipio "
            "identifier or explicit authoritative binding is required before Spiderweb "
            "ADMINISTRATIVE_SET migration."
        ),
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
