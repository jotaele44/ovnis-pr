"""OVNIS maintenance layer: detection, adapter, corrections."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maintenance import detect, run_maintenance  # noqa: E402
from maintenance import state as state_mod  # noqa: E402
from maintenance.adapters import local  # noqa: E402


def _write_jsonl(root, rel, rows):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _federation(root, **outputs):
    fed = {"program_id": "ovnis-pr", "canonical_outputs": outputs}
    (root / "federation.json").write_text(json.dumps(fed), encoding="utf-8")
    return state_mod.collect_repo_state(root)


def test_missing_federation_json_is_critical(tmp_path):
    state = state_mod.collect_repo_state(tmp_path)
    findings = detect.detect_missing_required_files("ovnis-pr", tmp_path, state)
    assert any(f.category == "manifest" and f.severity == "critical" for f in findings)


def test_provenance_ok_row_passes(tmp_path):
    _write_jsonl(tmp_path, "data/master/master_cases.jsonl", [
        {"record_id": "M1", "source_url": "https://x", "review_action": "promote",
         "latitude": 18.9, "longitude": -66.2, "location_confidence": 0.5},
    ])
    state = _federation(tmp_path, master_cases="data/master/master_cases.jsonl")
    assert local.check_case_provenance("ovnis-pr", tmp_path, state) == []


def test_missing_provenance_is_error(tmp_path):
    _write_jsonl(tmp_path, "data/master/master_cases.jsonl", [
        {"record_id": "M2", "review_action": "promote"},  # no source_*
    ])
    state = _federation(tmp_path, master_cases="data/master/master_cases.jsonl")
    findings = local.check_case_provenance("ovnis-pr", tmp_path, state)
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_coordinate_without_confidence_is_flagged(tmp_path):
    _write_jsonl(tmp_path, "data/master/master_cases.jsonl", [
        {"record_id": "M3", "source_url": "https://x", "review_action": "promote",
         "latitude": 18.9, "longitude": -66.2, "location_confidence": None},
    ])
    state = _federation(tmp_path, master_cases="data/master/master_cases.jsonl")
    findings = local.check_unknown_values_not_inferred("ovnis-pr", tmp_path, state)
    assert len(findings) == 1
    assert findings[0].category == "contradiction"


def test_audit_run_clean_repo_not_blocked(tmp_path):
    _write_jsonl(tmp_path, "data/master/master_cases.jsonl", [
        {"record_id": "M1", "source_url": "https://x", "review_action": "promote",
         "latitude": 18.9, "longitude": -66.2, "location_confidence": 0.5},
    ])
    _federation(tmp_path, master_cases="data/master/master_cases.jsonl")
    report = run_maintenance(root=tmp_path, mode="audit", write=False)
    assert report.promotion_blocked is False
