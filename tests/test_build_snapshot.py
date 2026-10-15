from __future__ import annotations

import json

import build_snapshot


def test_build_snapshot_shapes_offline_cases_like_api(tmp_path, monkeypatch):
    master = tmp_path / "master_cases.jsonl"
    candidates = tmp_path / "candidate_cases.jsonl"
    releases = tmp_path / "releases"
    out = tmp_path / "snapshot.json"
    master.write_text(
        json.dumps(
            {
                "record_id": "PRUFON-0001",
                "case_id": "PRUAP-0001",
                "date_local": "1975-03-04",
                "location_name": "Lajas",
                "municipality": "Lajas",
                "nearest_feature": "Laguna Cartagena",
                "latitude": 18.015,
                "longitude": -67.077,
                "evidence_tier": "T2",
                "case_confidence": 0.7,
                "source_citation": "fixture",
                "source_family": "test",
                "description": "fixture case",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    candidates.write_text("", encoding="utf-8")

    monkeypatch.setattr(build_snapshot, "MASTER_LEDGER", master)
    monkeypatch.setattr(build_snapshot, "CANDIDATE_LEDGER", candidates)
    monkeypatch.setattr(build_snapshot, "RELEASES_DIR", releases)
    monkeypatch.setattr(build_snapshot, "SNAPSHOT_OUT", out)

    assert build_snapshot.main() == 0
    snapshot = json.loads(out.read_text(encoding="utf-8"))

    case = snapshot["/cases"][0]
    assert case["date_raw"] == "1975-03-04"
    assert case["decade"] == "1970s"
    assert case["location_string"] == "Lajas · Lajas · Laguna Cartagena"
    assert case["location"]["lat"] == 18.015
    assert case["location"]["lon"] == -67.077
    assert snapshot["/health"]["data_status"] == "loaded"
    assert snapshot["/stats"]["geojsonSource"] == "derived_from_master_ledger"
    assert snapshot["/geojson"]["features"][0]["properties"]["location_string"] == case["location_string"]
