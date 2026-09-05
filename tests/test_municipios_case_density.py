"""GET /municipios/case_density — name join with a point-in-polygon fallback."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


def _backend():
    import server.backend.main as backend

    return backend


SQUARE_MUNICIPIO = {
    "type": "Feature",
    "properties": {"name": "Test Municipio", "geoid": "72999"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-67.0, 18.0], [-66.0, 18.0], [-66.0, 19.0], [-67.0, 19.0], [-67.0, 18.0]]],
    },
}


def _write_municipios(tmp_path: Path) -> Path:
    import json

    path = tmp_path / "municipios.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [SQUARE_MUNICIPIO]}))
    return path


def test_reconciliation_holds_against_real_ledger():
    """by_geoid's sum plus unmatched must always equal total_cases, whether
    or not the case ledger or municipios reference file is populated in this
    checkout — the same invariant used by aguayluz-pr's event_density and
    spiderweb-pr's gazetteer density endpoints."""
    from starlette.testclient import TestClient

    with TestClient(_backend().app) as client:
        resp = client.get("/municipios/case_density")
    assert resp.status_code == 200
    body = resp.json()
    assert sum(body["by_geoid"].values()) + body["unmatched"] == body["total_cases"]


def test_falls_back_to_point_in_polygon_when_name_does_not_match(tmp_path, monkeypatch):
    """Production case records carry coarse region labels ("southwest",
    "vieques") rather than real municipio names in `municipality`, so a name
    join alone would leave every case unmatched despite most of them
    carrying real coordinates. A case inside a municipio's polygon but with
    a non-matching (or absent) municipality label must still be counted."""
    backend = _backend()
    monkeypatch.setattr(backend, "MUNICIPIOS_PATH", _write_municipios(tmp_path))
    monkeypatch.setattr(
        backend,
        "all_cases",
        lambda: [
            {"municipality": "southwest", "latitude": 18.5, "longitude": -66.5},  # inside, name doesn't match
            {"municipality": None, "latitude": 18.5, "longitude": -66.5},  # inside, no name at all
            {"municipality": None, "latitude": 10.0, "longitude": -66.5},  # outside the polygon
            {"municipality": None, "latitude": None, "longitude": None},  # no coordinates either
        ],
    )

    from starlette.testclient import TestClient

    with TestClient(backend.app) as client:
        resp = client.get("/municipios/case_density")
    assert resp.status_code == 200
    body = resp.json()
    assert body["by_geoid"] == {"72999": 2}
    assert body["unmatched"] == 2
    assert body["total_cases"] == 4


def test_name_join_takes_priority_over_point_in_polygon(tmp_path, monkeypatch):
    backend = _backend()
    monkeypatch.setattr(backend, "MUNICIPIOS_PATH", _write_municipios(tmp_path))
    monkeypatch.setattr(
        backend,
        "all_cases",
        lambda: [{"municipality": "Test Municipio", "latitude": 10.0, "longitude": -66.5}],
    )

    from starlette.testclient import TestClient

    with TestClient(backend.app) as client:
        resp = client.get("/municipios/case_density")
    body = resp.json()
    assert body["by_geoid"] == {"72999": 1}
    assert body["unmatched"] == 0


def test_missing_municipios_file_reports_all_unmatched(tmp_path, monkeypatch):
    backend = _backend()
    monkeypatch.setattr(backend, "MUNICIPIOS_PATH", tmp_path / "does-not-exist.geojson")
    monkeypatch.setattr(
        backend,
        "all_cases",
        lambda: [{"municipality": "southwest", "latitude": 18.5, "longitude": -66.5}],
    )

    from starlette.testclient import TestClient

    with TestClient(backend.app) as client:
        resp = client.get("/municipios/case_density")
    body = resp.json()
    assert body == {"by_geoid": {}, "total_cases": 1, "unmatched": 1}
