"""Deterministic case reports (scripts/generate_case_report.py).

Positive: every report validates against its schema, its evidence ids resolve to
rows of the same federation export, and the same inputs give the same report
hash. Negative: a year-only date stays year-only, absent fields are reported as
not recorded rather than filled, and a source name in source_url is never
presented as a link.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

import generate_case_report as gcr
from federation_export import build_streams
from validate_research_ledgers import load_research

REPO = Path(__file__).resolve().parents[1]
MASTER = REPO / "data" / "master" / "master_cases.jsonl"
RESEARCH = REPO / "data" / "research"
SCHEMA = json.loads((REPO / "schemas" / "research" / "case_report.v1.schema.json").read_text(encoding="utf-8"))
NOW = "2026-10-03T00:00:00Z"


def _cases():
    return [json.loads(line) for line in MASTER.read_text(encoding="utf-8").splitlines() if line.strip()]


def _reports(created_at=NOW):
    return gcr.build_reports(_cases(), load_research(RESEARCH), master_path=MASTER, research_dir=RESEARCH,
                             created_at=created_at, git_sha="0" * 40)


def _empty_research():
    return {kind: [] for kind in load_research(RESEARCH)}


def _one(case, research=None):
    return gcr.build_report(case, research or _empty_research(), inputs={"data/master/master_cases.jsonl": "0" * 64},
                            snapshot_id="sha256:" + "0" * 64, created_at=NOW)


def test_every_real_report_validates_and_its_evidence_ids_resolve():
    reports = _reports()
    masters = [c for c in _cases() if c.get("record_type") == "master"]
    assert len(reports) == len(masters)
    streams = build_streams(_cases(), NOW)
    exported = {f"evo:{stream}:{row[key]}" for stream, key in
                (("entities", "entity_id"), ("observations", "observation_id"), ("sources", "source_id"))
                for row in streams[stream]}
    validator = Draft202012Validator(SCHEMA)
    for report in reports:
        assert list(validator.iter_errors(report)) == [], report["case_id"]
        assert set(report["evidence_ids"].values()) <= exported, report["case_id"]


def test_report_precision_matches_the_exported_declaration():
    streams = build_streams(_cases(), NOW)
    declared = {row["attributes"]["case_id"]: row["evidence_state"]["temporal_precision"] for row in streams["observations"]}
    for report in _reports():
        assert report["case"]["temporal_precision"] == declared[report["case_id"]]


def test_same_inputs_give_the_same_report_hash():
    first, second = _reports(), _reports(created_at="2030-01-01T00:00:00Z")
    assert [r["receipt"]["report_sha256"] for r in first] == [r["receipt"]["report_sha256"] for r in second]
    assert [r["receipt"]["run_id"] for r in first] == [r["receipt"]["run_id"] for r in second]
    assert first[0]["receipt"]["created_at"] != second[0]["receipt"]["created_at"]


def test_year_only_case_stays_year_only(master_case):
    report = _one(master_case(date_local="1967", municipality=None))
    assert report["case"]["date_local"] == "1967"
    assert report["case"]["temporal_precision"] == "YEAR_ONLY"
    gaps = [item["detail"] for item in report["unresolved"] if item["kind"] == "RECORD_GAP"]
    assert "date recorded only to the year" in gaps
    assert "municipality not recorded" in gaps
    assert "municipality" not in report["case"]


def test_absent_fields_are_not_invented(master_case):
    report = _one(master_case(description="", source_citation=None, object_type=None, time_local=None))
    assert report["narrative"] is None
    assert report["source"]["citation"] is None
    assert "object_type" not in report["case"] and "time_local" not in report["case"]
    assert {"kind": "RECORD_GAP", "detail": "narrative not recorded"} in report["unresolved"]
    assert "Not recorded." in gcr.render_markdown(report)


def test_source_name_in_source_url_is_not_a_link(master_case):
    report = _one(master_case(source_url="Inexplicata/Ovni.Net", source_citation=None))
    assert report["source"] == {"citation": None, "url": None, "locator": "Inexplicata/Ovni.Net", "family": "news_report"}
    assert "<Inexplicata" not in gcr.render_markdown(report)
    linked = _one(master_case())
    assert linked["source"]["url"] == "https://example.com/report" and linked["source"]["locator"] is None


def test_unadjudicated_candidate_is_unresolved_until_a_curator_decides(master_case):
    research = _empty_research()
    research["manifestation_candidate"] = [{"adjudication_id": "ADJ-C-1", "case_a": "PRUFON-0001", "case_b": "PRUFON-0002",
                                            "status": "CANDIDATE", "origin": "COMPUTED"}]
    report = _one(master_case(), research)
    assert report["linked"]["manifestation_candidates"] == ["ADJ-C-1"]
    assert any(i["kind"] == "UNADJUDICATED_DUPLICATE_CANDIDATE" and "PRUFON-0002" in i["detail"]
               for i in report["unresolved"])
    research["manifestation_adjudication"] = [{"adjudication_id": "ADJ-1", "case_a": "PRUFON-0002",
                                               "case_b": "PRUFON-0001", "status": "DISTINCT"}]
    decided = _one(master_case(), research)
    assert decided["linked"]["adjudications"] == ["ADJ-1"]
    assert not any(i["kind"] == "UNADJUDICATED_DUPLICATE_CANDIDATE" for i in decided["unresolved"])


def test_open_research_is_listed_as_unresolved(master_case):
    research = _empty_research()
    research["contradiction"] = [{"contradiction_id": "CONTRA-1", "case_ids": ["PRUFON-0001"], "status": "OPEN"}]
    research["research_queue_item"] = [{"item_id": "RQ-1", "case_ids": ["PRUFON-0001"], "status": "OPEN",
                                        "question": "Find the original page."}]
    research["hypothesis"] = [{"hypothesis_id": "HYP-1", "case_ids": ["PRUFON-0001"], "status": "OPEN"}]
    research["finding"] = [{"finding_id": "FIND-1", "source_refs": [{"case_id": "PRUFON-0001", "locator": "p1"}]}]
    report = _one(master_case(), research)
    kinds = {item["kind"] for item in report["unresolved"]}
    assert {"OPEN_CONTRADICTION", "OPEN_QUESTION", "OPEN_HYPOTHESIS"} <= kinds
    assert report["linked"]["findings"] == ["FIND-1"]


def test_cli_writes_json_and_markdown(tmp_path):
    case_id = next(c["case_id"] for c in _cases() if c.get("record_type") == "master")
    assert gcr.main(["--case", case_id, "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / f"{case_id}.json").read_text(encoding="utf-8"))
    assert report["case_id"] == case_id
    assert (tmp_path / f"{case_id}.md").read_text(encoding="utf-8").startswith(f"# Case report {case_id}")
    assert gcr.main(["--case", "NO-SUCH-CASE", "--out", str(tmp_path)]) == 1
