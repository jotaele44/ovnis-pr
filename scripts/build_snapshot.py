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
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.backend.payloads import data_status, feature_from_case, normalize_candidate, normalize_case  # noqa: E402

MASTER_LEDGER = REPO_ROOT / "data/master/master_cases.jsonl"
CANDIDATE_LEDGER = REPO_ROOT / "data/candidates/candidate_cases.jsonl"
RELEASES_DIR = REPO_ROOT / "releases"
SNAPSHOT_OUT = REPO_ROOT / "dashboard/src/lib/snapshot.json"
MUNICIPIOS_PATH = REPO_ROOT / "dashboard/public/geo/pr_municipios.geojson"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _is_placeholder(case: dict[str, Any]) -> bool:
    return case.get("source_family") == "placeholder" or case.get("record_id", "").endswith("-0000")


def _decade(date_str: str) -> str | None:
    try:
        year = int(str(date_str)[:4])
        return f"{(year // 10) * 10}s"
    except (ValueError, TypeError):
        return None


def _latest_geojson() -> Path | None:
    if not RELEASES_DIR.exists():
        return None
    candidates = sorted(RELEASES_DIR.glob("*/ovnis_cases_master.geojson"), reverse=True)
    return candidates[0] if candidates else None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _municipios_features() -> list[dict[str, Any]]:
    if not MUNICIPIOS_PATH.exists():
        return []
    return json.loads(MUNICIPIOS_PATH.read_text()).get("features", [])


def _municipios_name_to_geoid(features: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for feature in features:
        props = feature.get("properties") or {}
        name = props.get("name")
        geoid = props.get("geoid")
        if name and geoid:
            mapping[name] = str(geoid)
    return mapping


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Mirrors server/backend/main.py's _point_in_ring so the offline export
    snapshot matches what the live backend would compute."""
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _point_in_geometry(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    polygons = coords if gtype == "MultiPolygon" else [coords] if gtype == "Polygon" else []
    for rings in polygons:
        if not rings or not _point_in_ring(lon, lat, rings[0]):
            continue
        if not any(_point_in_ring(lon, lat, hole) for hole in rings[1:]):
            return True
    return False


def main() -> int:
    master = [normalize_case(c) for c in _read_jsonl(MASTER_LEDGER) if not _is_placeholder(c)]
    candidates = [normalize_candidate(c) for c in _read_jsonl(CANDIDATE_LEDGER) if not _is_placeholder(c)]

    mapped = [c for c in master if feature_from_case(c)]
    by_decade: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for case in master:
        d = _decade(case.get("date_local", ""))
        if d:
            by_decade[d] = by_decade.get(d, 0) + 1
        t = case.get("evidence_tier")
        if t:
            by_tier[t] = by_tier.get(t, 0) + 1

    municipios_features = _municipios_features()
    name_to_geoid = _municipios_name_to_geoid(municipios_features)
    by_geoid: dict[str, int] = {}
    unmatched = 0
    for case in master:
        name = case.get("municipality") or case.get("municipio")
        geoid = name_to_geoid.get(name) if name else None
        if geoid is None and _has_coords(case):
            lon, lat = float(case["longitude"]), float(case["latitude"])
            for feature in municipios_features:
                if _point_in_geometry(lon, lat, feature["geometry"]):
                    geoid = str((feature.get("properties") or {}).get("geoid"))
                    break
        if geoid is None:
            unmatched += 1
            continue
        by_geoid[geoid] = by_geoid.get(geoid, 0) + 1

    geojson_path = _latest_geojson()
    if geojson_path:
        geojson = json.loads(geojson_path.read_text())
    else:
        geojson = {"type": "FeatureCollection", "features": [feature_from_case(c) for c in mapped]}

    snapshot = {
        "/health": {
            "status": "ok",
            "master": len(master),
            "mapped": len(mapped),
            "unmapped": len(master) - len(mapped),
            "candidates": len(candidates),
            "data_status": data_status(master, candidates),
            "source_files": {
                "master": _display_path(MASTER_LEDGER),
                "candidates": _display_path(CANDIDATE_LEDGER),
                "geojson": _display_path(geojson_path) if geojson_path else "derived_from_master_ledger",
            },
        },
        "/cases": master,
        "/candidates": candidates,
        "/geojson": geojson,
        "/stats": {
            "total": len(master),
            "mapped": len(mapped),
            "unmapped": len(master) - len(mapped),
            "candidates": len(candidates),
            "byDecade": by_decade,
            "byTier": by_tier,
            "dataStatus": data_status(master, candidates),
            "geojsonSource": _display_path(geojson_path) if geojson_path else "derived_from_master_ledger",
        },
        "/municipios/case_density": {
            "by_geoid": by_geoid,
            "total_cases": len(master),
            "unmatched": unmatched,
        },
    }

    SNAPSHOT_OUT.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    print(f"wrote {SNAPSHOT_OUT} — {len(master)} master cases, {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
