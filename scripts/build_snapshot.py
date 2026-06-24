#!/usr/bin/env python3
"""Generate the offline dashboard snapshot for VITE_OFFLINE=1 builds.

Reads the master and candidate JSONL ledgers and writes a JSON object
keyed by API path to dashboard/src/lib/snapshot.json. Each key matches
a backend endpoint so the dashboard can serve itself without the FastAPI
server when built with VITE_OFFLINE=1.

Usage:
  python3 scripts/build_snapshot.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_LEDGER = REPO_ROOT / "data/master/master_cases.jsonl"
CANDIDATE_LEDGER = REPO_ROOT / "data/candidates/candidate_cases.jsonl"
RELEASES_DIR = REPO_ROOT / "releases"
SNAPSHOT_OUT = REPO_ROOT / "dashboard/src/lib/snapshot.json"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _is_placeholder(case: Dict[str, Any]) -> bool:
    return case.get("source_family") == "placeholder" or case.get("record_id", "").endswith("-0000")


def _has_coords(case: Dict[str, Any]) -> bool:
    lat = case.get("latitude")
    lon = case.get("longitude")
    return lat is not None and lon is not None and not (math.isnan(float(lat)) or math.isnan(float(lon)))


def _decade(date_str: str) -> Optional[str]:
    try:
        year = int(str(date_str)[:4])
        return f"{(year // 10) * 10}s"
    except (ValueError, TypeError):
        return None


def _latest_geojson() -> Optional[Path]:
    if not RELEASES_DIR.exists():
        return None
    candidates = sorted(RELEASES_DIR.glob("*/prufon_cases_master.geojson"), reverse=True)
    return candidates[0] if candidates else None


def _shape_for_api(case: Dict[str, Any]) -> Dict[str, Any]:
    """Add dashboard-expected derived fields (mirrors server/backend/main.py)."""
    date_local = case.get("date_local", "")
    lat = case.get("latitude")
    lon = case.get("longitude")
    shaped = dict(case)
    shaped["date_raw"] = date_local
    shaped["decade"] = _decade(date_local)
    shaped["location"] = {
        "lat": lat,
        "lon": lon,
        "string": case.get("location_name", ""),
        "municipality": case.get("municipality"),
    }
    shaped["location_string"] = case.get("location_name", "")
    return shaped


def _case_to_feature(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [case["longitude"], case["latitude"]]},
        "properties": {k: v for k, v in case.items() if k not in ("latitude", "longitude")},
    }


def main() -> int:
    master = [c for c in _read_jsonl(MASTER_LEDGER) if not _is_placeholder(c)]
    candidates = [c for c in _read_jsonl(CANDIDATE_LEDGER) if not _is_placeholder(c)]

    mapped = [c for c in master if _has_coords(c)]
    by_decade: Dict[str, int] = {}
    by_tier: Dict[str, int] = {}
    for case in master:
        d = _decade(case.get("date_local", ""))
        if d:
            by_decade[d] = by_decade.get(d, 0) + 1
        t = case.get("evidence_tier")
        if t:
            by_tier[t] = by_tier.get(t, 0) + 1

    geojson_path = _latest_geojson()
    if geojson_path:
        geojson = json.loads(geojson_path.read_text())
    else:
        geojson = {"type": "FeatureCollection", "features": [_case_to_feature(c) for c in mapped]}

    snapshot = {
        "/health": {
            "status": "ok",
            "master": len(master),
            "mapped": len(mapped),
            "unmapped": len(master) - len(mapped),
        },
        "/cases": [_shape_for_api(c) for c in master],
        "/candidates": candidates,
        "/geojson": geojson,
        "/stats": {
            "total": len(master),
            "mapped": len(mapped),
            "unmapped": len(master) - len(mapped),
            "byDecade": by_decade,
            "byTier": by_tier,
        },
    }

    SNAPSHOT_OUT.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    print(f"wrote {SNAPSHOT_OUT} — {len(master)} master cases, {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
