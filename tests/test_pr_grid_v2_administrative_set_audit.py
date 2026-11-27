"""Negative regressions: municipality syntax is not admission evidence."""
import json

import pytest
from federation.spatial import audit_pr_grid_v2_administrative_set as audit


@pytest.mark.parametrize(
    "row,expected",
    [
        ({"municipality": "San Juan"}, None),
        ({"municipality_geoid": "72127"}, "72127"),
        ({"municipality_geoid": "72999"}, "72999"),
        ({"municipality_geoid": "72127", "county_geoid": "72127"}, "72127"),
        ({"municipality_geoid": "72127", "county_geoid": "72001"}, None),
        ({"municipality_geoid": "72127", "county_geoid": "bad"}, None),
        ({"municipality_geoid": 72127}, None),
        ({"municipality_geoid": "72١٢٧"}, None),
        ({"municipality_geoid": "7212"}, None),
        ({"municipality_geoid": "01127"}, None),
        ({"latitude": 18.4, "longitude": -66.1}, None),
        (
            {
                "municipality_geoid": "72127",
                "Geometry_Evidence_State": "VERIFIED_ADMINISTRATIVE_GEOMETRY",
            },
            "72127",
        ),
    ],
)
def test_candidate_is_never_admission(row, expected):
    assert audit._syntactic_geoid(row) == expected
    assert audit._administrative_set_admissible(row) is False


def test_audit_separates_syntax_from_verified_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"record_type": "master", "municipality_geoid": "72127"},
        {"record_type": "master", "municipality_geoid": "72999"},
        {"record_type": "master", "municipality": "San Juan"},
        {"record_type": "candidate", "municipality_geoid": "72127"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    receipt = audit.audit(path)
    assert receipt["Master_Row_Count"] == 3
    assert receipt["Syntactic_Municipio_GEOID_Candidate_Row_Count"] == 2
    assert receipt["Stable_Municipio_GEOID_Row_Count"] == 0
    assert receipt["Administrative_Set_Admissible_Count"] == 0
    assert receipt["Authority_Receipt_Validation_State"] == "NOT_IMPLEMENTED"
    assert receipt["Migration_State"] == (
        "BLOCKED_AUTHORITATIVE_BINDING_VALIDATION_UNAVAILABLE"
    )
