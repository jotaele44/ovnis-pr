#!/usr/bin/env python3
"""Build a versioned release snapshot from the PRUFON master ledger.

Writes to releases/{YYYY-MM-DD}/:
  prufon_cases_master.geojson   GeoJSON FeatureCollection (mapped cases only)
  prufon_cases_master.csv       CSV of all master cases
  manifest.json                 Release metadata and checksums

Usage:
  python3 scripts/build_release.py
  python3 scripts/build_release.py --date 2025-01-15
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_LEDGER = REPO_ROOT / "data/master/master_cases.jsonl"
RELEASES_DIR = REPO_ROOT / "releases"

CSV_FIELDS = [
    "record_id", "case_id", "record_type", "date_local", "time_local",
    "location_name", "municipality", "latitude", "longitude",
    "environment", "object_type", "evidence_tier", "witness_type",
    "witness_count", "description", "language", "source_url",
    "source_citation", "source_family", "dedupe_status", "review_action",
    "case_confidence", "created_at", "updated_at",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_placeholder(case: Dict[str, Any]) -> bool:
    return case.get("source_family") == "placeholder" or case.get("record_id", "").endswith("-0000")


def _has_coords(case: Dict[str, Any]) -> bool:
    return case.get("latitude") is not None and case.get("longitude") is not None


def load_master() -> List[Dict[str, Any]]:
    cases = [json.loads(ln) for ln in MASTER_LEDGER.read_text().splitlines() if ln.strip()]
    return [c for c in cases if not _is_placeholder(c)]


def build_geojson(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for case in cases:
        if not _has_coords(case):
            continue
        props = {k: v for k, v in case.items() if k not in ("latitude", "longitude")}
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [case["longitude"], case["latitude"]],
            },
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": features}


def build_csv(cases: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for case in cases:
        writer.writerow({f: case.get(f, "") for f in CSV_FIELDS})
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a versioned PRUFON release snapshot.")
    ap.add_argument("--date", default=str(date.today()), help="Release date tag (YYYY-MM-DD)")
    ap.add_argument("--ledger", default=str(MASTER_LEDGER))
    ap.add_argument("--out", default=None, help="Output directory (default: releases/{date})")
    args = ap.parse_args()

    cases = load_master()
    if not cases:
        print("WARN — master ledger contains only placeholder rows; no release written.")
        return 0

    out_dir = Path(args.out) if args.out else RELEASES_DIR / args.date
    out_dir.mkdir(parents=True, exist_ok=True)

    geojson_data = build_geojson(cases)
    geojson_bytes = json.dumps(geojson_data, indent=2, sort_keys=True).encode()
    geojson_path = out_dir / "prufon_cases_master.geojson"
    geojson_path.write_bytes(geojson_bytes)

    csv_data = build_csv(cases)
    csv_bytes = csv_data.encode()
    csv_path = out_dir / "prufon_cases_master.csv"
    csv_path.write_bytes(csv_bytes)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    mapped = sum(1 for c in cases if _has_coords(c))
    manifest = {
        "release_date": args.date,
        "created_at": now,
        "producer": "prufon-pr",
        "case_count": len(cases),
        "mapped_count": mapped,
        "unmapped_count": len(cases) - mapped,
        "files": [
            {
                "filename": "prufon_cases_master.geojson",
                "record_count": len(geojson_data["features"]),
                "sha256": _sha256(geojson_bytes),
            },
            {
                "filename": "prufon_cases_master.csv",
                "record_count": len(cases),
                "sha256": _sha256(csv_bytes),
            },
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    print(f"wrote {out_dir} — {len(cases)} cases, {mapped} mapped, {len(geojson_data['features'])} geojson features")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
