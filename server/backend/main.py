#!/usr/bin/env python3
"""PRUFON FastAPI backend.

Reads the Git-native JSONL ledgers and release GeoJSON directly — no DB.
Run:  uvicorn server.backend.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MASTER_LEDGER = REPO_ROOT / "data/master/master_cases.jsonl"
CANDIDATE_LEDGER = REPO_ROOT / "data/candidates/candidate_cases.jsonl"
RELEASES_DIR = REPO_ROOT / "releases"

app = FastAPI(title="PRUFON API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _is_placeholder(case: Dict[str, Any]) -> bool:
    return case.get("source_family") == "placeholder" or case.get("record_id", "").endswith("-0000")


def _load_master() -> List[Dict[str, Any]]:
    return [c for c in _read_jsonl(MASTER_LEDGER) if not _is_placeholder(c)]


def _load_candidates() -> List[Dict[str, Any]]:
    return [c for c in _read_jsonl(CANDIDATE_LEDGER) if not _is_placeholder(c)]


def _has_coords(case: Dict[str, Any]) -> bool:
    lat = case.get("latitude")
    lon = case.get("longitude")
    return lat is not None and lon is not None and not (math.isnan(float(lat)) or math.isnan(float(lon)))


def _decade(date_str: str) -> Optional[str]:
    try:
        year = int(str(date_str)[:4])
        d = (year // 10) * 10
        return f"{d}s"
    except (ValueError, TypeError):
        return None


def _latest_geojson() -> Optional[Path]:
    if not RELEASES_DIR.exists():
        return None
    candidates = sorted(RELEASES_DIR.glob("*/prufon_cases_master.geojson"), reverse=True)
    return candidates[0] if candidates else None


def _case_to_feature(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [case["longitude"], case["latitude"]],
        },
        "properties": {k: v for k, v in case.items() if k not in ("latitude", "longitude")},
    }


def _matches_query(case: Dict[str, Any], q: str) -> bool:
    q_lower = q.lower()
    searchable = " ".join(filter(None, [
        case.get("description", ""),
        case.get("location_name", ""),
        case.get("municipality", ""),
        case.get("object_type", ""),
        case.get("witness_type", ""),
        case.get("source_citation", ""),
    ])).lower()
    return q_lower in searchable


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    master = _load_master()
    mapped = sum(1 for c in master if _has_coords(c))
    return {"status": "ok", "master": len(master), "mapped": mapped, "unmapped": len(master) - mapped}


@app.get("/cases")
def cases(
    decade: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    result = _load_master()
    if decade:
        result = [c for c in result if _decade(c.get("date_local", "")) == decade]
    if tier:
        result = [c for c in result if c.get("evidence_tier") == tier]
    if q:
        result = [c for c in result if _matches_query(c, q)]
    return result


@app.get("/cases/{case_id}")
def case_detail(case_id: str) -> Dict[str, Any]:
    for case in _load_master():
        if case.get("case_id") == case_id or case.get("record_id") == case_id:
            return case
    raise HTTPException(status_code=404, detail="Case not found")


@app.get("/candidates")
def candidates() -> List[Dict[str, Any]]:
    return _load_candidates()


@app.get("/geojson")
def geojson() -> Dict[str, Any]:
    geojson_path = _latest_geojson()
    if geojson_path:
        return json.loads(geojson_path.read_text())
    # Fall back to computing from master ledger in-memory
    features = [_case_to_feature(c) for c in _load_master() if _has_coords(c)]
    return {"type": "FeatureCollection", "features": features}


@app.get("/stats")
def stats() -> Dict[str, Any]:
    master = _load_master()
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
    return {
        "total": len(master),
        "mapped": len(mapped),
        "unmapped": len(master) - len(mapped),
        "byDecade": by_decade,
        "byTier": by_tier,
    }


@app.get("/search")
def search(q: str = Query(..., min_length=1)) -> List[Dict[str, Any]]:
    return [c for c in _load_master() if _matches_query(c, q)]
