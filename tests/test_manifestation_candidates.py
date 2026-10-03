"""Duplicate-manifestation candidate pairs (dedupe_candidates.py --master-pairs).

Positive: recorded dates that agree at the coarser precision plus a shared place
make a pair, and the committed pairs file is exactly what the generator writes.
Negative: different recorded municipalities, disagreeing dates or a missing date
never pair, and no pair is ever more than a COMPUTED CANDIDATE, however similar
its narratives.
"""

import json
from pathlib import Path

import dedupe_candidates as dd

REPO = Path(__file__).resolve().parents[1]
MASTER = REPO / "data" / "master" / "master_cases.jsonl"
PAIRS = REPO / "data" / "research" / "manifestation_candidates.jsonl"


def _case(case_id, date, municipality=None, location="Bahía de Mayagüez", description="Bright light over the bay."):
    return {"record_type": "master", "case_id": case_id, "date_local": date, "municipality": municipality,
            "location_name": location, "description": description, "source_url": f"https://example.org/{case_id}"}


def test_date_relation_respects_recorded_precision():
    assert dd.date_relation("1967-03-02", "1967-03-02") == "IDENTICAL_RECORDED_DATE"
    assert dd.date_relation("1967", "1967-03-02") == "COMPATIBLE_PRECISION"
    assert dd.date_relation("1967-03", "1967-03-02") == "COMPATIBLE_PRECISION"
    assert dd.date_relation("1967-03", "1967-04-02") is None
    assert dd.date_relation("1967", "1968") is None
    assert dd.date_relation("", "1967") is None


def test_place_basis_never_pairs_different_municipalities():
    a = _case("A", "1967", "Mayagüez", "Bahía")
    assert dd.place_basis(a, _case("B", "1967", "mayagüez ", "elsewhere")) == "MUNICIPALITY"
    assert dd.place_basis(a, _case("B", "1967", "Cabo Rojo", "Bahía")) is None
    assert dd.place_basis(_case("A", "1967"), _case("B", "1967")) == "LOCATION_TEXT"
    assert dd.place_basis(_case("A", "1967", location="Arecibo"), _case("B", "1967", location="Fajardo")) is None


def test_pairs_are_computed_candidates_however_similar():
    same = "Identical narrative of a hovering disc seen by two fishermen at dusk."
    pairs = dd.master_pairs([_case("PRUAP-0002", "1972-10-13", "Aguadilla", description=same),
                             _case("PRUAP-0001", "1972-10", "Aguadilla", description=same),
                             _case("PRUAP-0003", "1972-10-13", "Ponce", description=same),
                             _case("PRUAP-0004", None, "Aguadilla", description=same)])
    assert len(pairs) == 1
    pair = pairs[0]
    assert (pair["case_a"], pair["case_b"]) == ("PRUAP-0001", "PRUAP-0002")
    assert pair["status"] == "CANDIDATE" and pair["origin"] == "COMPUTED"
    assert pair["signals"] == {"date_relation": "COMPATIBLE_PRECISION", "place_basis": "MUNICIPALITY",
                               "narrative_similarity": 1.0, "same_source": False}
    assert pair["adjudication_id"].startswith("ADJ-C-")


def test_pairs_are_deterministic():
    cases = [json.loads(line) for line in MASTER.read_text(encoding="utf-8").splitlines() if line.strip()]
    first = dd.render_pairs(dd.master_pairs(cases))
    assert first == dd.render_pairs(dd.master_pairs(list(reversed(cases))))


def test_committed_pairs_file_is_current():
    assert dd.write_master_pairs(MASTER, PAIRS, check=True) == 0


def test_check_mode_reports_a_stale_file(tmp_path, capsys):
    master = tmp_path / "master.jsonl"
    master.write_text("".join(json.dumps(c) + "\n" for c in (_case("A", "1990", "Ponce"), _case("B", "1990", "Ponce"))),
                      encoding="utf-8")
    out = tmp_path / "pairs.jsonl"
    assert dd.main(["--master", str(master), "--master-pairs", "--pairs-output", str(out), "--check"]) == 1
    assert "is stale" in capsys.readouterr().out
    assert dd.main(["--master", str(master), "--master-pairs", "--pairs-output", str(out)]) == 0
    assert dd.main(["--master", str(master), "--master-pairs", "--pairs-output", str(out), "--check"]) == 0
    assert len(out.read_text(encoding="utf-8").splitlines()) == 1
