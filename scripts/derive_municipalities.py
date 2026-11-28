#!/usr/bin/env python3
"""Derive a municipio for each master case from its coordinates (report only).

No master case carries a real municipio name today: the ``municipality`` field
is either empty or a region label such as "southwest" or "island-wide". This
script tests each case's latitude/longitude against the 78 municipio polygons in
``dashboard/public/geo/pr_municipios.geojson`` and writes what it finds to
``reports/municipality_derivations.json``. It never edits a case.

A derived municipio is only as good as the coordinate it came from, and no case
records where its coordinate came from (see
``data/master/pr_grid_v2_coordinate_evidence_denominator.json``). Each derivation
is therefore labelled ``point_in_polygon_from_case_coordinate``, carries the
case's ``location_confidence``, and is a CANDIDATE for review, never source
evidence. Many coordinates are the centroid of a named place, so the report also
says whether the case's own ``location_name`` names the derived municipio
(``named_in_location``) and gives each row a ``review_class``:
``AGREES_WITH_LOCATION_NAME`` (the name and the polygon agree),
``GENERIC_LOCATION_DO_NOT_APPLY`` (the case is placed only at island, region or sea
level, or shares its exact coordinate with a case that is, so the coordinate is a
regional default point and the municipio it falls in must not be written to the
case), ``NAME_DISAGREES_WITH_POLYGON`` (the name names a different municipio),
``NEEDS_REVIEW``, ``CONFLICT`` or ``NOT_DERIVED``.

The point-in-polygon test is the one the backend's ``/municipios/case_density``
endpoint uses (``server/backend/main.py``), so the report and the map agree.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.backend.main import _point_in_geometry  # noqa: E402

from validate_case_ledgers import iter_jsonl  # noqa: E402

MASTER = ROOT / "data" / "master" / "master_cases.jsonl"
MUNICIPIOS = ROOT / "dashboard" / "public" / "geo" / "pr_municipios.geojson"
OUT = ROOT / "reports" / "municipality_derivations.json"

METHOD = "point_in_polygon_from_case_coordinate"
# location_confidence at or below this is flagged for review even when one polygon matches.
REVIEW_CONFIDENCE = 0.6


def load_municipios(path: Path = MUNICIPIOS) -> list[dict[str, Any]]:
    features = json.loads(path.read_text(encoding="utf-8")).get("features") or []
    municipios = []
    for feature in features:
        props = feature.get("properties") or {}
        name, geoid = props.get("name"), props.get("geoid")
        if not isinstance(name, str) or not name or geoid in (None, ""):
            raise ValueError("municipio feature requires non-empty name and geoid")
        municipios.append({"name": name, "geoid": str(geoid), "geometry": feature.get("geometry") or {}})
    return municipios


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _fold(text: str) -> str:
    """Lower-case and strip accents, so "Añasco" matches "Anasco" and "Bayamón" matches "Bayamon"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def named_in_location(municipio: str | None, location_name: Any) -> bool:
    """Whether the case's own location_name names the derived municipio."""
    if not municipio or not isinstance(location_name, str):
        return False
    return _fold(municipio) in _fold(location_name)


# Location names that place a case only at island, region or sea level. A coordinate for such a
# case is a regional default point, so whatever municipio it falls in says nothing about the case.
GENERIC_LOCATION_TERMS = (
    "unspecified",
    "vicinity",
    "airspace",
    "radar zone",
    "island-wide",
    "entire island",
    "offshore",
    "waters off",
    "near puerto rico",
    "over puerto rico",
    "east of puerto rico",
    "northern puerto rico",
    "southern puerto rico",
    "eastern puerto rico",
    "western puerto rico",
    "north coast",
    "south coast",
    "east coast",
    "west coast",
    "southeast coast",
    "southern area",
    "interior",
)


def is_generic_location(location_name: Any) -> bool:
    if not isinstance(location_name, str) or not location_name.strip():
        return True
    folded = _fold(location_name).strip()
    return folded in ("puerto rico", "pr") or any(term in folded for term in GENERIC_LOCATION_TERMS)


def other_municipios_named(row: dict[str, Any], municipio_names: set[str]) -> list[str]:
    """Municipios the location_name names, other than the derived one."""
    location = row["location_name"]
    if not isinstance(location, str):
        return []
    return sorted(
        name
        for name in municipio_names
        if name != row["derived_municipio"] and named_in_location(name, location)
    )


def review_class(row: dict[str, Any], on_default_point: bool) -> str:
    """How much review a derivation needs before anyone writes it to a case.

    ``on_default_point`` is true when another case at exactly the same coordinate has a
    generic location: that coordinate is a regional default, not this case's place.
    """
    if not row["derived_municipio"]:
        return "NOT_DERIVED"
    if row["outcome"] == "CONFLICTS_WITH_EXISTING":
        return "CONFLICT"
    if row["named_in_location"]:
        return "AGREES_WITH_LOCATION_NAME"
    if is_generic_location(row["location_name"]) or on_default_point:
        return "GENERIC_LOCATION_DO_NOT_APPLY"
    if row["other_municipios_named"]:
        return "NAME_DISAGREES_WITH_POLYGON"
    return "NEEDS_REVIEW"


def existing_class(value: Any, municipio_names: set[str]) -> str:
    if value in (None, "") or not str(value).strip():
        return "NULL"
    return "MUNICIPIO_NAME" if value in municipio_names else "NON_MUNICIPIO_LABEL"


def derive_case(case: dict[str, Any], municipios: list[dict[str, Any]]) -> dict[str, Any]:
    names = {m["name"] for m in municipios}
    existing = case.get("municipality")
    confidence = case.get("location_confidence")
    row: dict[str, Any] = {
        "case_id": case.get("case_id") or case.get("record_id"),
        "location_name": case.get("location_name"),
        "existing_municipality": existing,
        "existing_class": existing_class(existing, names),
        "location_confidence": confidence,
        "method": METHOD,
        "derived_municipio": None,
        "derived_geoid": None,
        "matched_municipios": [],
        "named_in_location": False,
        "other_municipios_named": [],
    }
    lat, lon = _number(case.get("latitude")), _number(case.get("longitude"))
    if lat is None or lon is None:
        row["outcome"] = "NO_COORDINATES"
        return row
    matches = [m for m in municipios if _point_in_geometry(lon, lat, m["geometry"])]
    row["matched_municipios"] = sorted(m["name"] for m in matches)
    if not matches:
        row["outcome"] = "OUTSIDE_MUNICIPIOS"
    elif len(matches) > 1:
        row["outcome"] = "AMBIGUOUS"
    else:
        row["derived_municipio"] = matches[0]["name"]
        row["derived_geoid"] = matches[0]["geoid"]
        low = _number(confidence) is None or float(confidence) <= REVIEW_CONFIDENCE
        row["outcome"] = "DERIVED_LOW_CONFIDENCE" if low else "DERIVED"
    row["named_in_location"] = named_in_location(row["derived_municipio"], row["location_name"])
    if row["existing_class"] == "MUNICIPIO_NAME" and row["derived_municipio"] not in (None, existing):
        row["outcome"] = "CONFLICTS_WITH_EXISTING"
    row["other_municipios_named"] = other_municipios_named(row, names)
    return row


def build_report(master: Path = MASTER, municipios_path: Path = MUNICIPIOS) -> dict[str, Any]:
    municipios = load_municipios(municipios_path)
    cases = iter_jsonl(master)
    rows = [derive_case(case, municipios) for case in cases]
    default_points = {
        (case.get("latitude"), case.get("longitude"))
        for case in cases
        if is_generic_location(case.get("location_name")) and _number(case.get("latitude")) is not None
    }
    for case, row in zip(cases, rows, strict=True):
        point = (case.get("latitude"), case.get("longitude"))
        row["review_class"] = review_class(row, point in default_points)
    return {
        "schema_version": "ovnis_municipality_derivations_v1",
        "state": "CANDIDATE_NOT_SOURCE_EVIDENCE",
        "method": METHOD,
        "review_confidence_threshold": REVIEW_CONFIDENCE,
        "inputs": {
            "master": str(master.relative_to(ROOT)) if master.is_relative_to(ROOT) else str(master),
            "municipios": (
                str(municipios_path.relative_to(ROOT))
                if municipios_path.is_relative_to(ROOT)
                else str(municipios_path)
            ),
            "municipio_count": len(municipios),
        },
        "summary": {
            "cases": len(rows),
            "by_outcome": dict(sorted(Counter(r["outcome"] for r in rows).items())),
            "by_existing_class": dict(sorted(Counter(r["existing_class"] for r in rows).items())),
            "by_review_class": dict(sorted(Counter(r["review_class"] for r in rows).items())),
            "derived_by_municipio": dict(
                sorted(Counter(r["derived_municipio"] for r in rows if r["derived_municipio"]).items())
            ),
        },
        "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--municipios", type=Path, default=MUNICIPIOS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    report = build_report(args.master, args.municipios)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
