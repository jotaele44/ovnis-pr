"""Read-only FastAPI backend for the OVNIS dashboard.

The Git ledgers remain the authority. This service does not mutate records and does
not infer production case counts from README copy; it reports the actual files on
disk, including placeholder-only ledgers.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "data" / "master" / "master_cases.jsonl"
CANDIDATE_PATH = ROOT / "data" / "candidates" / "candidate_cases.jsonl"
RELEASES_DIR = ROOT / "releases"

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


def first_present(row: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    """Return the first non-null/non-empty value without discarding explicit 0 values."""
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return default


def write_safe_int(value: Any) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def decade_from_date(value: Any) -> str | None:
    year = write_safe_int(value)
    if year is None:
        return None
    return f"{year // 10 * 10}s"


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def location_string(row: dict[str, Any]) -> str:
    parts = [
        row.get("location_name"),
        row.get("municipality"),
        row.get("nearest_feature"),
    ]
    return " · ".join(str(part) for part in parts if part) or "—"


def normalize_case(row: dict[str, Any]) -> dict[str, Any]:
    """Return dashboard-friendly case fields while preserving original ledger keys."""
    lat = as_float(row.get("latitude"))
    lon = as_float(row.get("longitude"))
    date_raw = row.get("date_raw") or row.get("date_local")
    case_id = row.get("case_id") or row.get("record_id")
    confidence = first_present(
        row,
        ("case_confidence", "chronology_confidence", "source_reliability"),
        "unknown",
    )

    normalized = dict(row)
    normalized.update(
        {
            "case_id": case_id,
            "date_raw": date_raw,
            "decade": row.get("decade") or decade_from_date(date_raw),
            "confidence": confidence,
            "location_string": location_string(row),
            "location": {
                "string": location_string(row),
                "municipality": row.get("municipality"),
                "nearest_feature": row.get("nearest_feature"),
                "lat": lat,
                "lon": lon,
                "confidence": row.get("location_confidence"),
            },
            "witness": {
                "class": row.get("witness_type"),
                "count": row.get("witness_count"),
                "name": row.get("witness_name"),
            },
            "evidence_type": row.get("evidence_type") or row.get("object_type"),
            "source": row.get("source_citation") or row.get("source_url") or row.get("source_family"),
            "contradictions_or_gaps": row.get("contradiction_note") or row.get("gap_note"),
            "reviewer_action": row.get("review_action"),
            "promoted_from": row.get("candidate_id"),
            "promoted_at": row.get("updated_at") or row.get("created_at"),
            "promoted_by": row.get("promoted_by"),
        }
    )
    return normalized


def normalize_candidate(row: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_case(row)
    normalized["candidate_id"] = row.get("candidate_id") or row.get("record_id")
    normalized["review_status"] = row.get("review_status") or row.get("review_action") or "pending"
    normalized["intake_channel"] = row.get("intake_channel") or row.get("source_family")
    return normalized


def all_cases() -> list[dict[str, Any]]:
    return [normalize_case(row) for row in read_jsonl(MASTER_PATH)]


def all_candidates() -> list[dict[str, Any]]:
    return [normalize_candidate(row) for row in read_jsonl(CANDIDATE_PATH)]


def latest_geojson_path() -> Path | None:
    if not RELEASES_DIR.exists():
        return None
    matches = sorted(RELEASES_DIR.rglob("ovnis_cases_master.geojson"))
    return matches[-1] if matches else None


def feature_from_case(case: dict[str, Any]) -> dict[str, Any] | None:
    location = case.get("location") or {}
    lat = as_float(location.get("lat"))
    lon = as_float(location.get("lon"))
    if lat is None or lon is None:
        return None
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "case_id": case.get("case_id"),
            "date_raw": case.get("date_raw"),
            "decade": case.get("decade"),
            "location_string": case.get("location_string"),
            "municipality": location.get("municipality"),
            "evidence_tier": case.get("evidence_tier"),
            "confidence": case.get("confidence"),
            "description": case.get("description"),
        },
    }


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


def is_placeholder(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("case_id", "candidate_id", "source_url", "source_citation", "description", "gap_note")
    ).lower()
    return "placeholder" in text or "ovnis-0000" in text or "cand-0000" in text


def data_status(cases: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
    if not cases and not candidates:
        return "empty"
    if cases and all(is_placeholder(row) for row in cases) and all(is_placeholder(row) for row in candidates):
        return "placeholder_only"
    return "loaded"


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


def matches_query(case: dict[str, Any], query: str) -> bool:
    query = query.lower().strip()
    haystack = " ".join(
        str(case.get(key) or "")
        for key in (
            "case_id",
            "record_id",
            "date_raw",
            "location_string",
            "municipality",
            "nearest_feature",
            "description",
            "description_en",
            "evidence_tier",
            "source",
        )
    ).lower()
    return query in haystack


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
