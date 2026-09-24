"""scripts/build_snapshot.py — the VITE_OFFLINE=1 export must match live shapes.

Master rows remain source-preserved. Candidate ledgers keep source rows intact,
but explicit placeholders are excluded from the retained /candidates universe.
Both live and offline surfaces expose source/retained/excluded arithmetic and
share main.py's is_placeholder()/data_status() semantics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("fastapi")

from server.backend.main import is_placeholder  # noqa: E402

import build_snapshot  # noqa: E402

PLACEHOLDER_ROW = {
    "record_id": "PRUFON-0001",
    "case_id": "PRUFON-0001",
    "date_local": "2024-06-15",
    "evidence_tier": "T2",
    "description": "placeholder entry pending real source material",
    "latitude": 18.2,
    "longitude": -66.5,
}


def test_placeholder_row_is_labeled_not_filtered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_placeholder(PLACEHOLDER_ROW), "fixture row must actually match main.py's own predicate"

    master_path = tmp_path / "master_cases.jsonl"
    master_path.write_text(json.dumps(PLACEHOLDER_ROW) + "\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate_cases.jsonl"
    candidate_path.write_text("", encoding="utf-8")
    snapshot_out = tmp_path / "snapshot.json"

    monkeypatch.setattr(build_snapshot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_snapshot, "MASTER_LEDGER", master_path)
    monkeypatch.setattr(build_snapshot, "CANDIDATE_LEDGER", candidate_path)
    monkeypatch.setattr(build_snapshot, "RELEASES_DIR", tmp_path / "releases")
    monkeypatch.setattr(build_snapshot, "SNAPSHOT_OUT", snapshot_out)
    monkeypatch.setattr(build_snapshot, "MUNICIPIOS_PATH", tmp_path / "no-municipios.geojson")

    assert build_snapshot.main() == 0
    snapshot = json.loads(snapshot_out.read_text())

    # The live backend never filters placeholder rows out of /cases — only
    # labels dataStatus — so the snapshot must match that, not silently drop it.
    assert snapshot["/cases"] == [PLACEHOLDER_ROW]
    assert snapshot["/stats"]["total"] == 1
    assert snapshot["/stats"]["dataStatus"] == "placeholder_only"

    # Fields previously missing from the offline snapshot entirely.
    assert snapshot["/stats"]["candidates"] == 0
    assert snapshot["/stats"]["geojsonSource"] == "derived_from_master_ledger"
    assert snapshot["/health"]["candidates"] == 0
    assert snapshot["/health"]["data_status"] == "placeholder_only"
    assert snapshot["/health"]["source_files"]["master"] == "master_cases.jsonl"


def test_candidate_placeholder_is_preserved_as_source_but_excluded_from_retained_universe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    master_path = tmp_path / "master_cases.jsonl"
    master_path.write_text("", encoding="utf-8")
    candidate_path = tmp_path / "candidate_cases.jsonl"
    candidate_path.write_text(
        json.dumps(
            {
                "record_id": "CAND-0000",
                "candidate_id": "CAND-0000",
                "record_type": "candidate",
                "description": "Placeholder candidate row used only to keep schema validation wired.",
                "source_url": "offline-placeholder",
                "source_citation": "placeholder only",
                "gap_note": "placeholder row; do not promote",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_out = tmp_path / "snapshot.json"

    monkeypatch.setattr(build_snapshot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_snapshot, "MASTER_LEDGER", master_path)
    monkeypatch.setattr(build_snapshot, "CANDIDATE_LEDGER", candidate_path)
    monkeypatch.setattr(build_snapshot, "RELEASES_DIR", tmp_path / "releases")
    monkeypatch.setattr(build_snapshot, "SNAPSHOT_OUT", snapshot_out)
    monkeypatch.setattr(build_snapshot, "MUNICIPIOS_PATH", tmp_path / "no-municipios.geojson")

    assert build_snapshot.main() == 0
    snapshot = json.loads(snapshot_out.read_text())

    assert snapshot["/candidates"] == []
    assert snapshot["/health"]["candidates"] == 0
    assert snapshot["/health"]["candidate_source_rows"] == 1
    assert snapshot["/health"]["candidate_excluded_placeholders"] == 1
    assert snapshot["/health"]["data_status"] == "placeholder_only"
    assert snapshot["/stats"]["candidates"] == 0
    assert snapshot["/stats"]["candidateSourceRows"] == 1
    assert snapshot["/stats"]["candidateExcludedPlaceholders"] == 1


def test_case_density_snapshot_matches_live_response_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """parseCaseDensity() in CaseMap.jsx requires matched_count and
    scope.identity_effect — the snapshot previously omitted both, so an
    offline build's Density toggle would throw when parsing the response."""
    municipio = {
        "type": "Feature",
        "properties": {"name": "Test Municipio", "geoid": "72999"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-67.0, 18.0], [-66.0, 18.0], [-66.0, 19.0], [-67.0, 19.0], [-67.0, 18.0]]],
        },
    }
    municipios_path = tmp_path / "municipios.geojson"
    municipios_path.write_text(json.dumps({"type": "FeatureCollection", "features": [municipio]}))

    master_path = tmp_path / "master_cases.jsonl"
    master_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"record_id": "A", "municipality": "Test Municipio", "latitude": 18.5, "longitude": -66.5},
                {"record_id": "B", "latitude": 10.0, "longitude": -66.5},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    candidate_path = tmp_path / "candidate_cases.jsonl"
    candidate_path.write_text("", encoding="utf-8")
    snapshot_out = tmp_path / "snapshot.json"

    monkeypatch.setattr(build_snapshot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_snapshot, "MASTER_LEDGER", master_path)
    monkeypatch.setattr(build_snapshot, "CANDIDATE_LEDGER", candidate_path)
    monkeypatch.setattr(build_snapshot, "RELEASES_DIR", tmp_path / "releases")
    monkeypatch.setattr(build_snapshot, "SNAPSHOT_OUT", snapshot_out)
    monkeypatch.setattr(build_snapshot, "MUNICIPIOS_PATH", municipios_path)

    assert build_snapshot.main() == 0
    density = json.loads(snapshot_out.read_text())["/municipios/case_density"]

    assert density["by_geoid"] == {"72999": 1}
    assert density["matched_count"] == 1
    assert density["unmatched"] == 1
    assert density["total_cases"] == 2
    assert density["scope"]["identity_effect"] == "NONE"
