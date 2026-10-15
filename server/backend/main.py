"""Read-only FastAPI backend for the OVNIS dashboard.

The Git ledgers remain the authority. This service does not mutate records and does
not infer production case counts from README copy; it reports the actual files on
disk, including placeholder-only ledgers.
"""

from __future__ import annotations

import json
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
import os
from fastapi.middleware.cors import CORSMiddleware

from server.backend.payloads import (
    data_status,
    feature_from_case,
    matches_query,
    normalize_candidate,
    normalize_case,
)

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "data" / "master" / "master_cases.jsonl"
CANDIDATE_PATH = ROOT / "data" / "candidates" / "candidate_cases.jsonl"
RELEASES_DIR = ROOT / "releases"
MUNICIPIOS_PATH = ROOT / "dashboard" / "public" / "geo" / "pr_municipios.geojson"

app = FastAPI(
    title="OVNIS Dashboard API",
    description="Thin read-only API over OVNIS JSONL ledgers and release GeoJSON.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        *[origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()],
    ],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL ledger, skipping blank lines and surfacing bad JSON clearly."""
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Invalid JSON in {path.relative_to(ROOT)} line {line_no}: {exc.msg}",
                ) from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def all_cases() -> list[dict[str, Any]]:
    return [normalize_case(row) for row in read_jsonl(MASTER_PATH)]


def all_candidates() -> list[dict[str, Any]]:
    return [normalize_candidate(row) for row in read_jsonl(CANDIDATE_PATH)]


def latest_geojson_path() -> Path | None:
    if not RELEASES_DIR.exists():
        return None
    matches = sorted(RELEASES_DIR.rglob("ovnis_cases_master.geojson"))
    return matches[-1] if matches else None


def release_geojson() -> dict[str, Any]:
    path = latest_geojson_path()
    if path is not None:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, dict) and value.get("type") == "FeatureCollection":
            return value
        raise HTTPException(
            status_code=500,
            detail=f"Invalid GeoJSON FeatureCollection in {path.relative_to(ROOT)}",
        )

    # Fallback for early/non-production repo state: derive mapped points from the
    # master ledger if coordinates exist. Placeholder rows therefore return empty.
    features = [feature for case in all_cases() if (feature := feature_from_case(case))]
    return {"type": "FeatureCollection", "features": features}


def stats_payload() -> dict[str, Any]:
    cases = all_cases()
    candidates = all_candidates()
    geojson = release_geojson()
    mapped = len(geojson.get("features") or [])
    by_decade = Counter(case.get("decade") or "unknown" for case in cases)
    by_tier = Counter(case.get("evidence_tier") or "unknown" for case in cases)
    return {
        "total": len(cases),
        "mapped": mapped,
        "unmapped": max(len(cases) - mapped, 0),
        "candidates": len(candidates),
        "byDecade": dict(by_decade),
        "byTier": dict(by_tier),
        "dataStatus": data_status(cases, candidates),
        "geojsonSource": str(latest_geojson_path().relative_to(ROOT)) if latest_geojson_path() else "derived_from_master_ledger",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    stats = stats_payload()
    return {
        "status": "ok",
        "master": stats["total"],
        "mapped": stats["mapped"],
        "unmapped": stats["unmapped"],
        "candidates": stats["candidates"],
        "data_status": stats["dataStatus"],
        "source_files": {
            "master": str(MASTER_PATH.relative_to(ROOT)),
            "candidates": str(CANDIDATE_PATH.relative_to(ROOT)),
            "geojson": stats["geojsonSource"],
        },
    }


@app.get("/cases")
def cases(
    decade: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    municipality: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    rows = all_cases()
    if decade and decade != "all":
        rows = [row for row in rows if row.get("decade") == decade]
    if tier and tier != "all":
        rows = [row for row in rows if row.get("evidence_tier") == tier]
    if municipality:
        m = municipality.lower()
        rows = [row for row in rows if m in str(row.get("municipality") or "").lower()]
    if q:
        rows = [row for row in rows if matches_query(row, q)]
    return rows


@app.get("/cases/{case_id}")
def case_detail(case_id: str) -> dict[str, Any]:
    for row in all_cases():
        if row.get("case_id") == case_id or row.get("record_id") == case_id:
            return row
    raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")


@app.get("/candidates")
def candidates() -> list[dict[str, Any]]:
    return all_candidates()


@app.get("/geojson")
def geojson() -> dict[str, Any]:
    return release_geojson()


@app.get("/stats")
def stats() -> dict[str, Any]:
    return stats_payload()


@app.get("/search")
def search(q: str = Query(default="")) -> list[dict[str, Any]]:
    q = q.strip()
    if not q:
        return []
    return [row for row in all_cases() if matches_query(row, q)]


def _municipios_features() -> list[dict[str, Any]]:
    if not MUNICIPIOS_PATH.is_file():
        return []
    with MUNICIPIOS_PATH.open("r", encoding="utf-8") as handle:
        doc = json.load(handle)
    return doc.get("features", [])


def _municipios_name_to_geoid(features: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    geoid_to_name: dict[str, str] = {}
    for feature in features:
        props = feature.get("properties") or {}
        name = props.get("name")
        geoid = props.get("geoid")
        if not isinstance(name, str) or not name or geoid in (None, ""):
            raise ValueError("municipio feature requires non-empty name and geoid")
        geoid = str(geoid)
        if name in mapping:
            raise ValueError(f"duplicate municipio name: {name}")
        if geoid in geoid_to_name:
            raise ValueError(f"duplicate municipio geoid: {geoid}")
        mapping[name] = geoid
        geoid_to_name[geoid] = name
    return mapping


def _source_manifestation(path: Path, row_count: int) -> dict[str, Any]:
    try:
        display_path = str(path.relative_to(ROOT))
    except ValueError:
        display_path = str(path)
    return {
        "path": display_path,
        "exists": path.exists(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
        "row_count": row_count,
    }


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Standard even-odd ray-casting test, run once per ring so a caller can
    apply it to a polygon's exterior and then its holes."""
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


@app.get("/municipios/case_density")
def municipios_case_density() -> dict[str, Any]:
    """Case count per municipio, keyed by GEOID, for the map's density
    choropleth.

    Tries a name join first — cases carry either a `municipality` or
    `municipio` field (schemas/case_record.schema.json) — the same
    name->GEOID `Counter` pattern aguayluz-pr's event_density and
    spiderweb-pr's gazetteer density endpoints use. In production this
    field is populated with coarse region labels ("southwest", "vieques",
    "island-wide") rather than real municipio names on every case that has
    it at all (over 80% are null), so the name join alone would report
    ~100% unmatched despite 364/470 cases actually carrying real
    coordinates. Falling back to a point-in-polygon test against each
    case's own latitude/longitude closes that gap with the corpus's most
    precise location data instead of leaving the choropleth empty.
    """
    features = _municipios_features()
    try:
        name_to_geoid = _municipios_name_to_geoid(features)
    except ValueError as exc:
        raise HTTPException(500, str(exc)) from exc
    by_geoid: Counter[str] = Counter()
    matched_by_method: Counter[str] = Counter()
    unresolved_by_reason: Counter[str] = Counter()
    cases = all_cases()
    for case in cases:
        name = case.get("municipality") or case.get("municipio")
        geoid = name_to_geoid.get(name) if name else None
        method = "exact_name" if geoid is not None else None
        if geoid is None:
            lat = as_float(case.get("latitude"))
            lon = as_float(case.get("longitude"))
            if lat is not None and lon is not None:
                candidates = [
                    str((feature.get("properties") or {}).get("geoid"))
                    for feature in features
                    if _point_in_geometry(lon, lat, feature.get("geometry") or {})
                ]
                candidates = [candidate for candidate in candidates if candidate not in ("", "None")]
                if len(candidates) == 1:
                    geoid = candidates[0]
                    method = "point_in_polygon"
                elif len(candidates) > 1:
                    unresolved_by_reason["AMBIGUOUS_POINT_IN_POLYGON"] += 1
                    continue
        if geoid is None:
            unresolved_by_reason[
                "NO_COORDINATES" if as_float(case.get("latitude")) is None or as_float(case.get("longitude")) is None else "OUTSIDE_MUNICIPIOS"
            ] += 1
            continue
        by_geoid[geoid] += 1
        matched_by_method[method or "UNRESOLVED_METHOD"] += 1
    matched_count = sum(by_geoid.values())
    unmatched = sum(unresolved_by_reason.values())
    return {
        "by_geoid": dict(by_geoid),
        "matched_count": matched_count,
        "matched_by_method": dict(matched_by_method),
        "total_cases": len(cases),
        "unmatched": unmatched,
        "unresolved_by_reason": dict(unresolved_by_reason),
        "scope": {
            "identity_effect": "NONE",
            "binding_effect": "AGGREGATION_ONLY",
            "name_normalization": "NONE",
            "geometry_predicate": "point_in_polygon",
            "state": "CANDIDATE_NOT_IDENTITY" if unmatched else "PASS",
        },
        "provenance": {
            "case_source": _source_manifestation(MASTER_PATH, len(cases)),
            "municipio_source": _source_manifestation(MUNICIPIOS_PATH, len(features)),
            "loaded_at": "request_time",
        },
    }
