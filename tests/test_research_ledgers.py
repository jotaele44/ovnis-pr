"""Research ledger validation (scripts/validate_research_ledgers.py).

Positive: the committed ledgers validate, and well-formed records of every kind
pass. Negative: each rule rejects the record it exists to stop: an unsourced
ACCEPTED finding, an INTERPRETIVE finding without a basis, a SUPPORTED
hypothesis with a check not run or FAILED, a record not recorded by a curator,
an unreviewed adjudication decision, a computed pair claiming more than
CANDIDATE, dangling references, and a record deleted since the base.
"""

import json
import subprocess
from pathlib import Path

import pytest

import validate_research_ledgers as vrl

REPO = Path(__file__).resolve().parents[1]
TS = "2026-10-01T12:00:00Z"
CHECKS = {name: {"status": "PASSED", "note": "checked"} for name in vrl.FALSIFICATION_CHECKS}


def _case(case_id):
    return {"record_id": case_id, "record_type": "master", "case_id": case_id}


@pytest.fixture
def workspace(tmp_path):
    research = tmp_path / "data" / "research"
    research.mkdir(parents=True)
    for filename, _ in vrl.LEDGERS.values():
        (research / filename).write_text("", encoding="utf-8")
    master = tmp_path / "master.jsonl"
    master.write_text("".join(json.dumps(_case(c)) + "\n" for c in ("PRUAP-0001", "PRUAP-0002")), encoding="utf-8")
    registry = tmp_path / "registry.csv"
    registry.write_text("source_id,name\nSRC-0001,El Vocero\n", encoding="utf-8")
    return tmp_path, research, master, registry


def _write(research, kind, *rows):
    filename = vrl.CANDIDATES_FILE if kind == vrl.CANDIDATES_KIND else vrl.LEDGERS[kind][0]
    (research / filename).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _errors(workspace, **kwargs):
    root, research, master, registry = workspace
    return vrl.validate(research, master_path=master, registry_path=registry, repo_root=root, **kwargs)


def _finding(**overrides):
    row = {
        "finding_id": "FIND-0001", "statement": "The case record cites a contemporaneous newspaper report.",
        "case_ids": ["PRUAP-0001"], "source_refs": [{"case_id": "PRUAP-0001", "locator": "p. 3"}],
        "status": "CANDIDATE", "epistemic_class": "CURATED", "origin": "CURATED",
        "recorded_by": "curator", "recorded_at": TS,
    }
    row.update(overrides)
    return row


def _hypothesis(**overrides):
    row = {
        "hypothesis_id": "HYP-0001", "statement": "The two reports describe one launch observed from two towns.",
        "case_ids": ["PRUAP-0001"], "finding_ids": [], "status": "OPEN",
        "falsification": {name: {"status": "NOT_RUN"} for name in vrl.FALSIFICATION_CHECKS},
        "origin": "CURATED", "recorded_by": "curator", "recorded_at": TS,
    }
    row.update(overrides)
    return row


def test_committed_ledgers_validate():
    assert vrl.validate() == []


def test_cli_reports_and_exits_zero(capsys):
    assert vrl.main([]) == 0
    assert "Errors: 0" in capsys.readouterr().out


def test_well_formed_records_of_every_kind_pass(workspace):
    _, research, _, _ = workspace
    _write(research, "research_topic", {"topic_id": "TOPIC-USO", "title": "Submerged objects", "scope": "USO reports",
                                        "status": "ACTIVE", "origin": "CURATED", "recorded_by": "c", "recorded_at": TS})
    _write(research, "finding", _finding(topic_ids=["TOPIC-USO"], status="ACCEPTED",
                                         review={"reviewed_by": "r", "reviewed_at": TS, "rationale": "matches source"}))
    _write(research, "hypothesis", _hypothesis(finding_ids=["FIND-0001"], status="SUPPORTED", falsification=CHECKS))
    _write(research, "contradiction", {
        "contradiction_id": "CONTRA-0001", "case_ids": ["PRUAP-0001"],
        "claim_a": {"text": "Seen at 20:30.", "source_ref": {"case_id": "PRUAP-0001", "locator": "para 1"}},
        "claim_b": {"text": "Seen at 22:00.", "source_ref": {"source_id": "SRC-0001", "locator": "p. 2"}},
        "status": "OPEN", "origin": "CURATED", "recorded_by": "c", "recorded_at": TS})
    _write(research, "manifestation_adjudication", {
        "adjudication_id": "ADJ-0001", "case_a": "PRUAP-0001", "case_b": "PRUAP-0002", "status": "DISTINCT",
        "origin": "CURATED", "reviewed_by": "r", "reviewed_at": TS, "rationale": "different witnesses and times"})
    _write(research, "research_queue_item", {
        "item_id": "RQ-0001", "question": "Obtain the original newspaper page.", "kind": "SOURCE_RETRIEVAL",
        "status": "OPEN", "case_ids": ["PRUAP-0001"], "origin": "CURATED", "recorded_by": "c", "recorded_at": TS})
    _write(research, "media_episode", {
        "episode_id": "EP-0001", "series": "Example Series", "season": 1, "episode": 2, "air_date": "2020-05",
        "title": "Lights over the bay", "primary_source_url": "https://example.org/ep2", "case_ids": ["PRUAP-0001"],
        "origin": "CURATED", "recorded_by": "c", "recorded_at": TS})
    assert _errors(workspace) == []


def test_unsourced_finding_cannot_be_accepted(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(status="ACCEPTED", source_refs=[]))
    assert any("ACCEPTED finding requires at least one source_ref and a review" in e for e in _errors(workspace))


def test_accepted_finding_needs_a_review(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(status="ACCEPTED"))
    assert any("requires at least one source_ref and a review" in e for e in _errors(workspace))


def test_interpretive_finding_needs_a_basis(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(epistemic_class="INTERPRETIVE"))
    assert any("INTERPRETIVE finding requires an interpretation_basis" in e for e in _errors(workspace))


def test_record_not_recorded_by_a_curator_is_rejected(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(origin="SEARCH_RESULT"))
    errors = _errors(workspace)
    assert any("never promoted from search output" in e for e in errors)


@pytest.mark.parametrize("bad", ["NOT_RUN", "FAILED"])
def test_supported_hypothesis_needs_every_check_run_and_none_failed(workspace, bad):
    _, research, _, _ = workspace
    checks = {**CHECKS, "background_prevalence": {"status": bad}}
    _write(research, "hypothesis", _hypothesis(status="SUPPORTED", falsification=checks))
    assert any("SUPPORTED hypothesis requires every falsification check run" in e and "background_prevalence" in e
               for e in _errors(workspace))


def test_hypothesis_must_carry_all_nine_checks(workspace):
    _, research, _, _ = workspace
    checks = dict(CHECKS)
    checks.pop("source_dependence")
    _write(research, "hypothesis", _hypothesis(falsification=checks))
    assert any("source_dependence" in e and "schema error" in e for e in _errors(workspace))


def test_superseded_record_names_its_successor(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(status="SUPERSEDED"))
    assert any("SUPERSEDED requires superseded_by naming another finding" in e for e in _errors(workspace))
    _write(research, "finding", _finding(status="SUPERSEDED", superseded_by="FIND-0002"),
           _finding(finding_id="FIND-0002"))
    assert _errors(workspace) == []


def test_curated_adjudication_must_be_a_reviewed_decision(workspace):
    _, research, _, _ = workspace
    _write(research, "manifestation_adjudication", {
        "adjudication_id": "ADJ-0001", "case_a": "PRUAP-0001", "case_b": "PRUAP-0002", "status": "SAME_EVENT",
        "origin": "CURATED"})
    assert any("SAME_EVENT requires reviewed_by and rationale" in e for e in _errors(workspace))
    _write(research, "manifestation_adjudication", {
        "adjudication_id": "ADJ-0001", "case_a": "PRUAP-0001", "case_b": "PRUAP-0002", "status": "CANDIDATE",
        "origin": "CURATED"})
    assert any("must decide SAME_EVENT, DISTINCT or UNRESOLVABLE" in e for e in _errors(workspace))


def test_computed_pair_is_never_more_than_a_candidate(workspace):
    _, research, _, _ = workspace
    pair = {"adjudication_id": "ADJ-C-ABC", "case_a": "PRUAP-0001", "case_b": "PRUAP-0002", "status": "SAME_EVENT",
            "origin": "COMPUTED", "method": "m",
            "signals": {"date_relation": "IDENTICAL_RECORDED_DATE", "place_basis": "MUNICIPALITY",
                        "narrative_similarity": 0.99, "same_source": True}}
    _write(research, vrl.CANDIDATES_KIND, pair)
    assert any("similarity never decides identity" in e for e in _errors(workspace))


def test_adjudication_pairs_two_different_cases(workspace):
    _, research, _, _ = workspace
    _write(research, "manifestation_adjudication", {
        "adjudication_id": "ADJ-0001", "case_a": "PRUAP-0001", "case_b": "PRUAP-0001", "status": "DISTINCT",
        "origin": "CURATED", "reviewed_by": "r", "rationale": "x"})
    assert any("pairs two different cases" in e for e in _errors(workspace))


def test_dangling_references_are_rejected(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(case_ids=["PRUAP-9999"], topic_ids=["TOPIC-NONE"],
                                         source_refs=[{"source_id": "SRC-0404", "locator": "x"}]))
    _write(research, "hypothesis", _hypothesis(finding_ids=["FIND-0404"], falsification={
        **{name: {"status": "NOT_RUN"} for name in vrl.FALSIFICATION_CHECKS},
        "missing_data": {"status": "PASSED", "evidence_refs": ["nowhere"]}}))
    errors = _errors(workspace)
    for expected in ("unknown case id 'PRUAP-9999'", "unknown research_topic id 'TOPIC-NONE'",
                     "unknown source id 'SRC-0404'", "unknown finding id 'FIND-0404'", "evidence ref 'nowhere'"):
        assert any(expected in e for e in errors), expected


def test_duplicate_ids_are_rejected(workspace):
    _, research, _, _ = workspace
    _write(research, "finding", _finding(), _finding())
    assert any("duplicate finding_id 'FIND-0001'" in e for e in _errors(workspace))


def test_deleted_record_fails_the_retention_check(workspace):
    root, research, _, _ = workspace
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    _write(research, "finding", _finding())
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"], cwd=root, check=True)
    assert _errors(workspace, base="HEAD") == []

    _write(research, "finding")  # the finding is removed instead of being retired by status
    errors = _errors(workspace, base="HEAD")
    assert any("'FIND-0001' existed at HEAD and is gone" in e for e in errors)

    _write(research, "finding", _finding(status="REJECTED"))  # retiring it by status is allowed
    assert _errors(workspace, base="HEAD") == []


def test_invalid_json_is_reported(workspace):
    _, research, _, _ = workspace
    (research / "findings.jsonl").write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="findings.jsonl:1: invalid JSON"):
        _errors(workspace)
