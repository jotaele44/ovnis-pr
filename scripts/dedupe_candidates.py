#!/usr/bin/env python3
"""Generate a preliminary OVNIS dedupe report.

This is a conservative review-queue generator. It does not merge or promote cases.
"""

from __future__ import annotations

import argparse
import csv
import json
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def date_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a[:7] == b[:7]:
        return 0.75
    if a[:4] == b[:4]:
        return 0.40
    return 0.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def location_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    an = str(a.get("location_name") or "").lower()
    bn = str(b.get("location_name") or "").lower()
    name_sim = SequenceMatcher(None, an, bn).ratio() if an and bn else 0.0

    if all(isinstance(x, (int, float)) for x in [a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")]):
        km = haversine_km(float(a["latitude"]), float(a["longitude"]), float(b["latitude"]), float(b["longitude"]))
        geo = 1.0 if km <= 1 else 0.75 if km <= 5 else 0.50 if km <= 20 else 0.0
        return max(name_sim, geo)
    return name_sim


def text_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    ad = str(a.get("description") or "").lower()
    bd = str(b.get("description") or "").lower()
    return SequenceMatcher(None, ad, bd).ratio() if ad and bd else 0.0


def source_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    if a.get("source_url") and a.get("source_url") == b.get("source_url"):
        return 1.0
    if a.get("source_family") and a.get("source_family") == b.get("source_family"):
        return 0.35
    return 0.0


def match_score(candidate: dict[str, Any], master: dict[str, Any]) -> float:
    ds = date_score(str(candidate.get("date_local") or ""), str(master.get("date_local") or ""))
    ls = location_score(candidate, master)
    ts = text_score(candidate, master)
    ss = source_score(candidate, master)
    return round((ds * 0.35) + (ls * 0.30) + (ts * 0.20) + (ss * 0.15), 3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OVNIS dedupe review report")
    parser.add_argument("--candidates", default="data/candidates/candidate_cases.jsonl")
    parser.add_argument("--master", default="data/master/master_cases.jsonl")
    parser.add_argument("--output", default="reports/dedupe_candidates.csv")
    parser.add_argument("--threshold", type=float, default=0.55)
    args = parser.parse_args()

    candidates = iter_jsonl(Path(args.candidates))
    masters = iter_jsonl(Path(args.master))
    rows: list[dict[str, Any]] = []

    for cand in candidates:
        best: tuple[float, dict[str, Any] | None] = (0.0, None)
        for master in masters:
            score = match_score(cand, master)
            if score > best[0]:
                best = (score, master)
        if best[0] >= args.threshold and best[1] is not None:
            status = "possible_duplicate" if best[0] < 0.85 else "duplicate"
            rows.append({
                "candidate_id": cand.get("candidate_id") or cand.get("record_id"),
                "matched_case_id": best[1].get("case_id") or best[1].get("record_id"),
                "match_score": best[0],
                "recommended_status": status,
                "candidate_date": cand.get("date_local"),
                "master_date": best[1].get("date_local"),
                "candidate_location": cand.get("location_name"),
                "master_location": best[1].get("location_name"),
            })

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "candidate_id",
            "matched_case_id",
            "match_score",
            "recommended_status",
            "candidate_date",
            "master_date",
            "candidate_location",
            "master_location",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} dedupe review rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
