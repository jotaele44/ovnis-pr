import json

import resolve_road_refs as rr


def _case(case_id, **fields):
    base = {"case_id": case_id, "location_name": None, "nearest_feature": None, "description": None, "municipality": None}
    base.update(fields)
    return base


def test_pr_pattern_in_location():
    refs = rr.resolve_case(_case("A", location_name="Sierra Bermeja, Lajas, Puerto Rico (Route PR-303)"))
    assert [(r["route_ref"], r["route_number_band"], r["match_kind"]) for r in refs] == [("PR-303", "tertiary_band", "pr_pattern")]
    assert refs[0]["confidence"] == 0.8


def test_generic_english_route():
    refs = rr.resolve_case(_case("B", location_name="Route 52 near Lake Carraizo, Caguas, Puerto Rico", municipality="Caguas"))
    assert [(r["route_ref"], r["route_number_band"], r["match_kind"]) for r in refs] == [("PR-52", "primary_band", "generic_english")]
    assert refs[0]["confidence"] == 0.5
    assert refs[0]["case_municipality"] == "Caguas"


def test_location_wins_over_description():
    refs = rr.resolve_case(_case("C", location_name="PR-3 Hwy, Guayama", description="Later seen near road 191."))
    assert [(r["field"], r["route_ref"]) for r in refs] == [("location_name", "PR-3")]


def test_description_fallback_and_ramal_and_km():
    refs = rr.resolve_case(_case("D", location_name="El Yunque", description="Stopped on Carr. 3R Km 5 Hm 2, later on road 191."))
    assert [(r["route_ref"], r["is_ramal"]) for r in refs] == [("PR-3R", True), ("PR-191", False)]
    assert refs[0]["km"] == 5.2


def test_no_road_reference():
    assert rr.resolve_case(_case("E", location_name="Cabo Rojo lighthouse", description="Route/delivery route, no number.")) == []


def test_main_writes_report_without_touching_master(tmp_path):
    master = tmp_path / "master.jsonl"
    rows = [_case("A", location_name="Route PR-303"), _case("E", location_name="Offshore")]
    master.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    before = master.read_bytes()
    out = tmp_path / "road_refs.json"
    assert rr.main(["--master", str(master), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert (report["cases_scanned"], report["cases_with_road_ref"], report["road_refs"]) == (2, 1, 1)
    assert master.read_bytes() == before
