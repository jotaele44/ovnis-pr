"""Shared dashboard payload shaping for live API and offline snapshots."""

from __future__ import annotations

from typing import Any


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
