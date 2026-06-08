import json
from pathlib import Path

import pytest

from validate_case_ledgers import core_validate, iter_jsonl, validate


def _errs(case):
    errors, _ = core_validate(case, path=Path("ledger.jsonl"), line_no=1)
    return errors


def test_valid_master_has_no_core_errors(master_case):
    assert _errs(master_case()) == []


def test_missing_required_field_flagged(master_case):
    case = master_case()
    case.pop("source_url")
    assert any("source_url" in e for e in _errs(case))


def test_invalid_evidence_tier(master_case):
    assert any("evidence_tier" in e for e in _errs(master_case(evidence_tier="T9")))


def test_invalid_record_type(master_case):
    assert any("record_type" in e for e in _errs(master_case(record_type="bogus")))


def test_invalid_dedupe_status(master_case):
    assert any("dedupe_status" in e for e in _errs(master_case(dedupe_status="maybe")))


def test_invalid_review_action(master_case):
    assert any("review_action" in e for e in _errs(master_case(review_action="later")))


def test_date_patterns(master_case):
    for good in ("2024", "2024-06", "2024-06-15"):
        assert _errs(master_case(date_local=good)) == []
    assert any("date_local" in e for e in _errs(master_case(date_local="06/15/2024")))


def test_time_pattern_invalid(master_case):
    assert any("time_local" in e for e in _errs(master_case(time_local="25:00")))


def test_generic_location_rejected(master_case):
    assert any("generic" in e for e in _errs(master_case(location_name="Puerto Rico")))


def test_master_requires_case_id(master_case):
    case = master_case()
    case.pop("case_id")
    assert any("case_id" in e for e in _errs(case))


def test_master_review_action_restricted(master_case):
    assert any("promote or merge" in e for e in _errs(master_case(review_action="monitor")))


def test_master_dedupe_not_checked_rejected(master_case):
    assert any("not_checked" in e for e in _errs(master_case(dedupe_status="not_checked")))


def test_description_min_length(master_case):
    assert any("20 characters" in e for e in _errs(master_case(description="short")))


def test_iter_jsonl_malformed_raises(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"record_id": "x"}\n{not json}\n')
    with pytest.raises(ValueError):
        iter_jsonl(p)


def test_iter_jsonl_non_object_row_raises(tmp_path):
    p = tmp_path / "arr.jsonl"
    p.write_text('[1, 2, 3]\n')
    with pytest.raises(ValueError):
        iter_jsonl(p)


def test_validate_clean_ledger_returns_0(master_case, tmp_path):
    p = tmp_path / "master.jsonl"
    p.write_text(json.dumps(master_case()) + "\n")
    # nonexistent schema path -> schema validation skipped; isolates core+dup logic
    assert validate([p], tmp_path / "nope.schema.json") == 0


def test_validate_duplicate_record_id_returns_1(master_case, tmp_path):
    p = tmp_path / "master.jsonl"
    a = master_case(record_id="PRUFON-DUP", case_id="PRUFON-DUP")
    b = master_case(record_id="PRUFON-DUP", case_id="PRUFON-DUP2")
    p.write_text(json.dumps(a) + "\n" + json.dumps(b) + "\n")
    assert validate([p], tmp_path / "nope.schema.json") == 1


def test_validate_missing_ledger_returns_1(tmp_path):
    assert validate([tmp_path / "absent.jsonl"], tmp_path / "nope.schema.json") == 1
