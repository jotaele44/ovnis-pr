import json

import corpus_quality_report as cq


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_master_metrics_count_presence_not_placeholders():
    rows = [
        {
            "source_url": "https://example.org/a",
            "source_family": "none",
            "source_citation": "",
            "municipality": "Lajas",
            "latitude": 18.0,
            "longitude": -67.0,
            "location_confidence": 0.7,
            "evidence_tier": "T3",
            "created_at": "2026-06-23T00:00:00Z",
        },
        {
            "source_url": "label only",
            "source_family": "U.S. Navy",
            "source_citation": "Deck log p. 4",
            "municipality": None,
            "latitude": None,
            "longitude": -66.0,
            "location_confidence": None,
            "evidence_tier": "T1",
            "coordinate_method": "source_stated",
            "created_at": "2026-07-01T00:00:00Z",
        },
    ]
    metrics = cq.master_metrics(rows)
    assert metrics["rows"] == 2
    present = metrics["provenance_field_present"]
    assert present["source_url"] == 2
    assert present["source_family"] == 1  # "none" is not a source family
    assert present["source_citation"] == 1
    assert present["municipality"] == 1
    assert present["source_hash"] == 0
    assert metrics["coordinate_pair_count"] == 1  # a lone longitude is not a pair
    assert metrics["coordinate_provenance_row_count"] == 1
    assert metrics["location_confidence_counts"] == {"0.7": 1, "null": 1}
    assert metrics["evidence_tier_counts"] == {"T1": 1, "T3": 1}
    assert metrics["created_month_counts"] == {"2026-06": 1, "2026-07": 1}


def test_candidate_metrics_separate_placeholder_rows():
    rows = [{"candidate_id": "CAND-0000"}, {"candidate_id": "CAND-0001"}]
    assert cq.candidate_metrics(rows) == {"rows": 2, "placeholder_rows": 1, "real_rows": 1}


def test_main_writes_report_and_leaves_inputs_alone(tmp_path, capsys):
    master = tmp_path / "master.jsonl"
    candidates = tmp_path / "candidates.jsonl"
    research = tmp_path / "research"
    research.mkdir()
    _write_jsonl(master, [{"case_id": "A", "latitude": 18.1, "longitude": -66.1}])
    _write_jsonl(candidates, [{"candidate_id": "CAND-0000"}])
    (research / "findings.jsonl").write_text("", encoding="utf-8")
    _write_jsonl(research / "manifestation_candidates.jsonl", [{"id": 1}, {"id": 2}])
    adjudication = tmp_path / "adj.csv"
    adjudication.write_text("adjudication_state\nDISCOVERY_ONLY\nDISCOVERY_ONLY\nREVIEW_TIE\n", encoding="utf-8")
    before = master.read_bytes()
    out = tmp_path / "out" / "report.json"

    rc = cq.main(
        [
            "--master", str(master),
            "--candidates", str(candidates),
            "--research-dir", str(research),
            "--adjudication", str(adjudication),
            "--out", str(out),
        ]
    )

    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out) == report
    assert report["master"]["rows"] == 1
    assert report["candidates"]["real_rows"] == 0
    assert report["research_ledger_rows"] == {"findings": 0, "manifestation_candidates": 2}
    assert report["source_reference_adjudication_states"] == {"DISCOVERY_ONLY": 2, "REVIEW_TIE": 1}
    assert master.read_bytes() == before


def test_missing_adjudication_file_is_empty(tmp_path):
    assert cq.adjudication_metrics(tmp_path / "absent.csv") == {}


def test_committed_corpus_report_runs():
    report = cq.build_report()
    assert report["master"]["rows"] >= 470
    assert report["master"]["coordinate_pair_count"] <= report["master"]["rows"]
