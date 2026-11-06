#!/usr/bin/env python3
"""Find Puerto Rico road references in OVNIS case records (report only).

Reads the master case ledger and, for each case, looks for road references such
as "Route PR-303", "PR-3 Hwy", "Carr. 3 Km 5" or "road 191". It writes a report;
it never edits, merges or promotes a case.

Route parsing comes from the pinned spiderweb-pr module
``federation/roads/pr_route_ref.py`` (see its pin JSON). That module only knows
Puerto Rico spellings (PR-n, Carretera n, Ruta n, ...). OVNIS sources are often
English and say just "Route 52" or "road 191", so this script adds one pattern of
its own for those. Its hits are tagged ``match_kind: "generic_english"`` and get a
lower confidence, because a bare "Route 52" could also be a non-PR road.

Fields are searched in order location_name, nearest_feature, description; the
first field with a hit wins, and all distinct routes in that field are reported.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "federation" / "roads"))

import pr_route_ref  # noqa: E402

FIELDS = ("location_name", "nearest_feature", "description")

GENERIC_ENGLISH = re.compile(r"\b(?:ROUTE|ROAD|RD|HWY|HIGHWAY)\s*\.?\s*#?\s*(\d{1,4}[A-Z]?)\b", re.I)
# The pinned patterns, applied with finditer so a field naming several routes
# ("Hwy 2 ... PR-3") yields each of them.
PR_PATTERNS = pr_route_ref.ROUTE_PATTERNS

CONFIDENCE = {"pr_pattern": 0.8, "generic_english": 0.5}


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _hits(text: str) -> list[tuple[str, str, str]]:
    """Return (route_number, match_kind, matched_text) for each distinct route in text."""
    found: dict[str, tuple[str, str, str]] = {}
    for pat in PR_PATTERNS:
        for m in pat.finditer(text):
            rn = m.group(1).upper()
            found.setdefault(rn, (rn, "pr_pattern", m.group(0)))
    for m in GENERIC_ENGLISH.finditer(text):
        rn = m.group(1).upper()
        found.setdefault(rn, (rn, "generic_english", m.group(0)))
    return sorted(found.values(), key=lambda h: text.find(h[2]))


def resolve_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    for field in FIELDS:
        text = case.get(field)
        if not isinstance(text, str) or not text.strip():
            continue
        hits = _hits(text)
        if not hits:
            continue
        out = []
        for rn, kind, matched in hits:
            base, suffix = pr_route_ref.split_route_number(rn)
            out.append({
                "case_id": case.get("case_id") or case.get("record_id"),
                "field": field,
                "matched_text": matched,
                "route_number": rn,
                "route_ref": f"PR-{rn}",
                "route_number_band": pr_route_ref.route_number_band(base) if base else "unknown",
                "is_ramal": suffix == pr_route_ref.RAMAL_SUFFIX,
                "km": pr_route_ref.km_marker_from_text(text),
                "case_municipality": case.get("municipality"),
                "match_kind": kind,
                "confidence": CONFIDENCE[kind],
                "status": "COMPUTED_CANDIDATE",
            })
        return out
    return []


def build_report(cases: list[dict[str, Any]], source: str) -> dict[str, Any]:
    refs = [ref for case in cases for ref in resolve_case(case)]
    by_field: dict[str, int] = {}
    by_band: dict[str, int] = {}
    for ref in refs:
        by_field[ref["field"]] = by_field.get(ref["field"], 0) + 1
        by_band[ref["route_number_band"]] = by_band.get(ref["route_number_band"], 0) + 1
    return {
        "report": "ovnis_road_refs",
        "source": source,
        "parser_pin": "federation/roads/pr_route_ref.pin.json",
        "cases_scanned": len(cases),
        "cases_with_road_ref": len({r["case_id"] for r in refs}),
        "road_refs": len(refs),
        "by_field": by_field,
        "by_band": by_band,
        "note": "Computed candidates for review. Case records are not modified.",
        "refs": refs,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--master", default=str(ROOT / "data" / "master" / "master_cases.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "road_refs.json"))
    args = ap.parse_args(argv)
    master = Path(args.master)
    report = build_report(iter_jsonl(master), str(master.relative_to(ROOT)) if master.is_relative_to(ROOT) else str(master))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['road_refs']} road refs in {report['cases_with_road_ref']} of {report['cases_scanned']} cases -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
