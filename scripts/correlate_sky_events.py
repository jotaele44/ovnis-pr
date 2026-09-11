#!/usr/bin/env python3
"""Build a bounded OVNIS × Skywatcher sky-event candidate ledger.

Discovery is deliberately conservative: exact or partial calendar overlap may
create a candidate edge, but temporal proximity never establishes identity.
The resulting edge begins UNRESOLVED until independently computed evidence gates
are supplied by Skywatcher and adjudicated under the correlation contract.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

FINAL_CASE_STATES = (
    "MATCHED",
    "PARTIAL",
    "CONTRADICTED_ONLY",
    "UNRESOLVED",
    "NO_ELIGIBLE_SKY_DATA",
)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def validate_unique(rows: Iterable[dict], key: str, label: str) -> None:
    values = [row.get(key) for row in rows]
    missing = [idx + 1 for idx, value in enumerate(values) if not value]
    if missing:
        raise ValueError(f"{label}: missing {key} at rows {missing[:10]}")
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"{label}: duplicate {key}: {duplicates[:10]}")


def _date_precision(value: str | None) -> int:
    if not value:
        return 0
    parts = value.split("-")
    if len(parts) == 3 and all(parts):
        return 3
    if len(parts) == 2 and all(parts):
        return 2
    if len(parts) == 1 and len(parts[0]) == 4:
        return 1
    return 0


def calendar_overlap(case_date: str | None, event_date: str | None) -> bool:
    """Return True only when represented calendar components do not conflict."""
    pc = _date_precision(case_date)
    pe = _date_precision(event_date)
    if not pc or not pe:
        return False
    c = case_date.split("-")
    e = event_date.split("-")
    shared = min(pc, pe)
    return c[:shared] == e[:shared]


def event_local_date(event: dict) -> str | None:
    # Current federation sky event artifacts preserve local time separately but
    # UTC date is safe only for discovery when local date is not explicitly
    # provided. Production ephemeris correlation must provide observer-local date.
    raw = event.get("local_date")
    if raw:
        return raw
    start = event.get("start_utc")
    return start[:10] if isinstance(start, str) and len(start) >= 10 else None


def build_ledger(cases: list[dict], events: list[dict]) -> dict:
    validate_unique(cases, "case_id", "cases")
    validate_unique(events, "sky_event_id", "events")

    edges: list[dict] = []
    cases_with_candidate: set[str] = set()

    for case in cases:
        case_id = case["case_id"]
        case_date = case.get("date_local")
        for event in events:
            event_date = event_local_date(event)
            if not calendar_overlap(case_date, event_date):
                continue
            cases_with_candidate.add(case_id)
            edges.append(
                {
                    "correlation_id": f"{case_id}__{event['sky_event_id']}",
                    "case_id": case_id,
                    "sky_event_id": event["sky_event_id"],
                    "discovery_basis": "CALENDAR_OVERLAP_ONLY",
                    "classification": "UNRESOLVED",
                    "gate_results": {
                        gate: {"state": "UNKNOWN", "evidence": [], "notes": None}
                        for gate in (
                            "time", "visibility", "location", "azimuth", "elevation",
                            "trajectory", "duration", "appearance", "upstream_identity"
                        )
                    },
                    "contradictions": [],
                    "unresolved_fields": [
                        "time", "visibility", "location", "azimuth", "elevation",
                        "trajectory", "duration", "appearance", "upstream_identity"
                    ],
                    "source_manifestations": [event.get("source_url_canonical") or event.get("source_url_raw")],
                    "skywatcher_artifact_version": None,
                    "adjudicated_utc": None,
                }
            )

    no_eligible = len(cases) - len(cases_with_candidate)
    disposition = {
        "MATCHED": 0,
        "PARTIAL": 0,
        "CONTRADICTED_ONLY": 0,
        "UNRESOLVED": len(cases_with_candidate),
        "NO_ELIGIBLE_SKY_DATA": no_eligible,
    }
    assert sum(disposition.values()) == len(cases)

    return {
        "scope": "bounded supplied sky-event manifestation set",
        "certification_state": "PROVISIONAL",
        "case_count": len(cases),
        "sky_event_count": len(events),
        "candidate_edge_count": len(edges),
        "case_disposition": disposition,
        "arithmetic_closed": True,
        "identity_warning": "Calendar overlap is discovery only and is never identity proof.",
        "edges": edges,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--sky-events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_ledger(read_jsonl(args.cases), read_jsonl(args.sky_events))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
