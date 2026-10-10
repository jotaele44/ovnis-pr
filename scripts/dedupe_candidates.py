#!/usr/bin/env python3
"""Generate OVNIS dedupe review queues.

Two conservative review-queue generators; neither merges, promotes or edits a case.

* Default: score each intake candidate against the master ledger and write a CSV.
* ``--master-pairs``: pair master cases that may record the same event and write
  ``data/research/manifestation_candidates.jsonl``. A pair needs recorded dates that
  agree at the coarser of their two precisions AND the same place (the same
  municipality, or, when either case has none, near-identical location text).
  Narrative similarity and a shared source are recorded as signals for the reviewer.
  Every pair is a COMPUTED CANDIDATE: similarity never decides identity, and only a
  curator's reviewed entry in ``manifestation_adjudications.jsonl`` can.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
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


MASTER_PAIR_METHOD = "ovnis-master-pair-blocking-v1"
MASTER_PAIRS_OUTPUT = "data/research/manifestation_candidates.jsonl"
LOCATION_TEXT_RATIO = 0.85


def _clean(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def date_relation(a: str, b: str) -> str | None:
    """How two recorded dates agree, or None. "1967" agrees with "1967-03-02" at year
    precision; a finer date is never derived from a coarser one."""
    if not a or not b:
        return None
    if a == b:
        return "IDENTICAL_RECORDED_DATE"
    shorter, longer = sorted((a, b), key=len)
    return "COMPATIBLE_PRECISION" if longer.startswith(shorter) else None


def place_basis(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """The place two cases share, or None. Two different recorded municipalities never pair."""
    muni_a, muni_b = _clean(a.get("municipality")), _clean(b.get("municipality"))
    if muni_a and muni_b:
        return "MUNICIPALITY" if muni_a == muni_b else None
    loc_a, loc_b = _clean(a.get("location_name")), _clean(b.get("location_name"))
    if loc_a and loc_b and SequenceMatcher(None, loc_a, loc_b).ratio() >= LOCATION_TEXT_RATIO:
        return "LOCATION_TEXT"
    return None


def _case_key(case: dict[str, Any]) -> str:
    return str(case.get("case_id") or case.get("record_id"))


def master_pairs(masters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Candidate duplicate-manifestation pairs among master cases, sorted and deterministic."""
    cases = sorted((m for m in masters if m.get("record_type") == "master"), key=_case_key)
    rows: list[dict[str, Any]] = []
    for a, b in itertools.combinations(cases, 2):
        relation = date_relation(str(a.get("date_local") or ""), str(b.get("date_local") or ""))
        if relation is None:
            continue
        basis = place_basis(a, b)
        if basis is None:
            continue
        case_a, case_b = sorted((_case_key(a), _case_key(b)))
        digest = hashlib.sha256(f"{case_a}|{case_b}".encode()).hexdigest()[:12].upper()
        rows.append({
            "adjudication_id": f"ADJ-C-{digest}",
            "case_a": case_a,
            "case_b": case_b,
            "status": "CANDIDATE",
            "origin": "COMPUTED",
            "method": MASTER_PAIR_METHOD,
            "signals": {
                "date_relation": relation,
                "place_basis": basis,
                "narrative_similarity": round(text_score(a, b), 3),
                "same_source": bool(a.get("source_url")) and a.get("source_url") == b.get("source_url"),
            },
        })
    return sorted(rows, key=lambda row: (row["case_a"], row["case_b"]))


def render_pairs(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)


def write_master_pairs(master: Path, output: Path, *, check: bool = False) -> int:
    text = render_pairs(master_pairs(iter_jsonl(master)))
    count = text.count("\n")
    if check:
        current = output.read_text(encoding="utf-8") if output.exists() else None
        if current != text:
            print(f"{output} is stale; regenerate it with: python3 scripts/dedupe_candidates.py --master-pairs")
            return 1
        print(f"{output} is current ({count} candidate pairs)")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"Wrote {count} candidate pairs to {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate OVNIS dedupe review queues")
    parser.add_argument("--candidates", default="data/candidates/candidate_cases.jsonl")
    parser.add_argument("--master", default="data/master/master_cases.jsonl")
    parser.add_argument("--output", default="reports/dedupe_candidates.csv")
    parser.add_argument("--threshold", type=float, default=0.55)
    parser.add_argument("--master-pairs", action="store_true",
                        help="pair master cases that may record the same event (CANDIDATE only)")
    parser.add_argument("--pairs-output", default=MASTER_PAIRS_OUTPUT)
    parser.add_argument("--check", action="store_true",
                        help="with --master-pairs: fail if the committed pairs file is stale")
    args = parser.parse_args(argv)

    if args.master_pairs:
        return write_master_pairs(Path(args.master), Path(args.pairs_output), check=args.check)

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
