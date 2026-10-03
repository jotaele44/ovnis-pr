"""Research rows in the federation export (federation_export.build_research_streams).

Positive: curated records become typed entity rows with declared evidence
state and links, computed pairs become CANDIDATE edges, and every case gets a
report. Negative: empty ledgers emit no research rows, a computed pair carries
the weak match_basis that keeps it a candidate in the Hub, a curated decision
replaces its computed pair, and a link to an unknown case is dropped rather
than pointed at an invented entity.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

import federation_export as fe
from prii_export_utils import fid

REPO = Path(__file__).resolve().parents[1]
NOW = "2026-10-03T00:00:00Z"
TS = "2026-10-01T12:00:00Z"


def _declaration_validator():
    schema = json.loads((REPO / "schemas" / "federation_epistemic_state.v1.schema.json").read_text(encoding="utf-8"))
    wrapper = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/producer_declaration"}
    return Draft202012Validator(wrapper)


def _research(**rows):
    research = {kind: [] for kind in fe.LEDGERS}
    research[fe.CANDIDATES_KIND] = []
    research.update(rows)
    return research


def _pair(a="PRUFON-0001", b="PRUFON-0002"):
    return {"adjudication_id": "ADJ-C-0001", "case_a": a, "case_b": b, "status": "CANDIDATE", "origin": "COMPUTED",
            "method": "ovnis-master-pair-blocking-v1",
            "signals": {"date_relation": "IDENTICAL_RECORDED_DATE", "place_basis": "MUNICIPALITY",
                        "narrative_similarity": 0.4, "same_source": False}}


def _cases(master_case):
    return [master_case(), master_case(record_id="PRUFON-0002", case_id="PRUFON-0002")]


def _by_type(streams, stream, key):
    out = {}
    for row in streams[stream]:
        out.setdefault(row[key], []).append(row)
    return out


def test_empty_ledgers_emit_no_research_rows(master_case):
    streams = fe.build_research_streams(_cases(master_case), _research(), NOW)
    assert streams == {"sources": [], "entities": [], "relationships": []}


def test_computed_pair_is_a_candidate_edge(master_case):
    streams = fe.build_research_streams(_cases(master_case), _research(manifestation_candidate=[_pair()]), NOW)
    entities = _by_type(streams, "entities", "entity_type")
    rels = _by_type(streams, "relationships", "relationship_type")
    (adjudication,) = entities["manifestation_adjudication"]
    assert adjudication["attributes"]["status"] == "CANDIDATE"
    assert adjudication["evidence_state"]["epistemic_class"] == "COMPUTED"
    (edge,) = rels["candidate_duplicate_of"]
    assert edge["match_basis"] == "co_occurrence"
    assert edge["source_entity_id"] == fid("ent", "case", "PRUFON-0001")
    assert edge["target_entity_id"] == fid("ent", "case", "PRUFON-0002")
    assert len(rels["about_case"]) == 2
    (source,) = streams["sources"]
    assert source["source_type"] == "computed_derivation" and "dedupe_candidates.py" in source["source_ref"]


def test_curated_decision_replaces_its_computed_pair(master_case):
    decision = {"adjudication_id": "ADJ-0001", "case_a": "PRUFON-0002", "case_b": "PRUFON-0001", "status": "SAME_EVENT",
                "origin": "CURATED", "reviewed_by": "r", "reviewed_at": TS, "rationale": "same witness, same night"}
    streams = fe.build_research_streams(
        _cases(master_case), _research(manifestation_candidate=[_pair()], manifestation_adjudication=[decision]), NOW)
    rels = _by_type(streams, "relationships", "relationship_type")
    assert "candidate_duplicate_of" not in rels
    (same,) = rels["same_event_as"]
    assert "match_basis" not in same and same["adjudication_id"] == "ADJ-0001"
    (adjudication,) = _by_type(streams, "entities", "entity_type")["manifestation_adjudication"]
    assert adjudication["evidence_state"]["epistemic_class"] == "CURATED"


def test_curated_records_carry_declared_state_and_links(master_case):
    finding = {"finding_id": "FIND-0001", "statement": "The witness account names the date and the vessel.",
               "topic_ids": ["TOPIC-USO"], "case_ids": ["PRUFON-0001"],
               "source_refs": [{"case_id": "PRUFON-0001", "locator": "p. 3"}], "status": "CANDIDATE",
               "epistemic_class": "INTERPRETIVE", "interpretation_basis": "reading of the witness statement",
               "origin": "CURATED", "recorded_by": "c", "recorded_at": TS}
    hypothesis = {"hypothesis_id": "HYP-0001", "statement": "One object was reported from two towns.",
                  "case_ids": ["PRUFON-0001", "PRUFON-0404"], "finding_ids": ["FIND-0001"], "status": "OPEN",
                  "origin": "CURATED", "recorded_by": "c", "recorded_at": TS}
    topic = {"topic_id": "TOPIC-USO", "title": "Submerged objects", "scope": "USO", "status": "ACTIVE",
             "origin": "CURATED", "recorded_by": "c", "recorded_at": TS}
    streams = fe.build_research_streams(
        _cases(master_case), _research(finding=[finding], hypothesis=[hypothesis], research_topic=[topic]), NOW)
    entities = {row["entity_type"]: row for row in streams["entities"]}
    assert {"data_stage": "FINDING", "epistemic_class": "INTERPRETIVE",
            "interpretation_basis": "reading of the witness statement"}.items() <= entities["finding"]["evidence_state"].items()
    assert entities["hypothesis"]["evidence_state"]["data_stage"] == "INTERPRETATION"
    assert entities["hypothesis"]["evidence_state"]["epistemic_class"] == "INTERPRETIVE"
    assert entities["hypothesis"]["evidence_state"]["interpretation_basis"]
    assert entities["research_topic"]["external_ids"] == {"ovnis_topic_id": "TOPIC-USO"}
    rels = {(r["relationship_type"], r["source_entity_id"], r["target_entity_id"]) for r in streams["relationships"]}
    finding_id, hypothesis_id = entities["finding"]["entity_id"], entities["hypothesis"]["entity_id"]
    case = fid("ent", "case", "PRUFON-0001")
    assert ("about_case", finding_id, case) in rels
    assert ("in_topic", finding_id, entities["research_topic"]["entity_id"]) in rels
    assert ("tests", hypothesis_id, finding_id) in rels
    cites = [r for r in streams["relationships"] if r["relationship_type"] == "cites"]
    assert len(cites) == 1 and cites[0]["locator"] == "p. 3"
    # PRUFON-0404 is not a case: no edge points at an invented entity.
    assert ("about_case", hypothesis_id, fid("ent", "case", "PRUFON-0404")) not in rels
    assert {row["source_type"] for row in streams["sources"]} == {"research_ledger"}


def test_every_case_gets_a_report(master_case, tmp_path):
    cases = _cases(master_case)
    master = tmp_path / "master.jsonl"
    master.write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    reports = fe.build_reports(cases, _research(), master_path=master, research_dir=tmp_path, created_at=NOW)
    streams = fe.build_research_streams(cases, _research(), NOW, reports=reports)
    report_rows = [e for e in streams["entities"] if e["entity_type"] == "case_report"]
    assert [r["external_ids"]["ovnis_case_id"] for r in report_rows] == ["PRUFON-0001", "PRUFON-0002"]
    assert all(r["evidence_state"]["data_stage"] == "REPORT" for r in report_rows)
    assert report_rows[0]["attributes"]["report"]["case_id"] == "PRUFON-0001"


def test_research_rows_declare_valid_evidence_state(master_case, tmp_path):
    validator = _declaration_validator()
    cases = _cases(master_case)
    master = tmp_path / "master.jsonl"
    master.write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    finding = {"finding_id": "FIND-0001", "statement": "A sourced statement about the case.", "case_ids": ["PRUFON-0001"],
               "source_refs": [{"case_id": "PRUFON-0001", "locator": "p. 1"}], "status": "CANDIDATE",
               "epistemic_class": "CURATED", "origin": "CURATED", "recorded_by": "c", "recorded_at": TS}
    hypothesis = {"hypothesis_id": "HYP-0001", "statement": "A hypothesis about the case.", "case_ids": ["PRUFON-0001"],
                  "status": "OPEN", "origin": "CURATED", "recorded_by": "c", "recorded_at": TS}
    research = _research(manifestation_candidate=[_pair()], finding=[finding], hypothesis=[hypothesis])
    reports = fe.build_reports(cases, research, master_path=master, research_dir=tmp_path, created_at=NOW)
    streams = fe.build_research_streams(cases, research, NOW, reports=reports)
    for stream in ("sources", "entities", "relationships"):
        for row in streams[stream]:
            assert list(validator.iter_errors(row["evidence_state"])) == [], row
            for field in ("source_id", "confidence", "lineage", "synthetic", "created_at", "extracted_at"):
                assert field in row
            assert row["source_id"].startswith("src_")


def test_production_export_includes_research_rows(tmp_path, monkeypatch):
    out = tmp_path / "export"
    monkeypatch.setattr("sys.argv", ["federation_export.py", "--mode", "production", "--out", str(out)])
    assert fe.main() == 0
    entities = [json.loads(line) for line in (out / "entities.jsonl").read_text(encoding="utf-8").splitlines()]
    types = {e["entity_type"] for e in entities}
    assert {"uap_case", "case_report", "manifestation_adjudication"} <= types
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert {f["stream"] for f in manifest["files"]} == {"sources", "entities", "relationships", "observations"}
