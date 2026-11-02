"""OVNIS PR Grid V2 coordinate evidence stays fail-closed."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/master/master_cases.jsonl"
RECEIPT = ROOT / "data/master/pr_grid_v2_coordinate_evidence_denominator.json"
AUDITOR = ROOT / "federation/spatial/audit_pr_grid_v2_coordinate_evidence.py"

SPEC = importlib.util.spec_from_file_location("ovnis_grid_v2_coordinate_audit", AUDITOR)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()


def test_frozen_master_ledger_identity_and_coordinate_denominator_close():
    receipt = _receipt()
    payload = LEDGER.read_bytes()
    assert receipt["Source_Git_Blob_SHA1"] == _git_blob_sha1(payload)
    assert receipt["Source_Git_Blob_SHA1"] == "428990a32070295f1efe7a7779e4b0e9f7200e82"

    audit = mod.audit(LEDGER)
    for field in (
        "Total_Row_Count",
        "Master_Row_Count",
        "Numeric_Coordinate_Pair_Count",
        "Missing_Or_NonNumeric_Coordinate_Pair_Count",
        "Verified_Source_Coordinate_Marker_Count",
        "Exact_Source_Point_Admissible_Count",
        "Coordinate_Provenance_Field_Row_Count",
        "Location_Confidence_Counts",
    ):
        assert receipt[field] == audit[field]

    assert receipt["Master_Row_Count"] == 470
    assert receipt["Numeric_Coordinate_Pair_Count"] == 469
    assert receipt["Missing_Or_NonNumeric_Coordinate_Pair_Count"] == 1


def test_coordinate_presence_and_confidence_do_not_promote_exactness():
    receipt = _receipt()
    assert receipt["Verified_Source_Coordinate_Marker_Count"] == 0
    assert receipt["Exact_Source_Point_Admissible_Count"] == 0
    assert receipt["Coordinate_Provenance_Field_Row_Count"] == 0
    assert receipt["Coordinate_Presence_Is_Exact_Evidence"] is False
    assert receipt["Location_Confidence_Is_Exact_Evidence"] is False
    assert receipt["Evidence_Tier_Is_Exact_Coordinate_Evidence"] is False
    assert receipt["Required_Evidence_State"] == "VERIFIED_SOURCE_COORDINATE"
    assert (
        receipt["Migration_State"]
        == "BLOCKED_NO_VERIFIED_SOURCE_COORDINATE_DENOMINATOR"
    )
    assert receipt["Promotion_State"] == "CANDIDATE_NOT_CANONICAL"
    assert receipt["Identity_Default"] == "CANDIDATE_NOT_IDENTITY"


def test_generated_federation_observation_export_is_not_a_committed_denominator():
    receipt = _receipt()
    assert receipt["Source_Exporter_Geometry_Precision_State"] == "UNKNOWN"
    assert receipt["Generated_Federation_Exports_Committed"] is False
    assert not (ROOT / "exports/federation/observations.jsonl").exists()
    assert not (ROOT / "exports/federation/manifest.json").exists()
