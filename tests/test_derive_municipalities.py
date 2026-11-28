import json

import derive_municipalities as dm

SQUARE_A = {"type": "Polygon", "coordinates": [[[-67.0, 18.0], [-66.5, 18.0], [-66.5, 18.5], [-67.0, 18.5], [-67.0, 18.0]]]}
SQUARE_B = {"type": "Polygon", "coordinates": [[[-66.5, 18.0], [-66.0, 18.0], [-66.0, 18.5], [-66.5, 18.5], [-66.5, 18.0]]]}
MUNICIPIOS = [
    {"name": "Añasco", "geoid": "72011", "geometry": SQUARE_A},
    {"name": "Bayamón", "geoid": "72021", "geometry": SQUARE_B},
]


def _case(case_id, lat, lon, location_name, **fields):
    row = {"case_id": case_id, "latitude": lat, "longitude": lon, "location_name": location_name,
           "municipality": None, "location_confidence": 0.7}
    row.update(fields)
    return row


def test_derives_and_matches_name_without_accents():
    row = dm.derive_case(_case("A", 18.2, -66.8, "Barrio Hatillo, Anasco"), MUNICIPIOS)
    assert (row["outcome"], row["derived_municipio"], row["derived_geoid"]) == ("DERIVED", "Añasco", "72011")
    assert row["named_in_location"] is True
    assert row["method"] == dm.METHOD


def test_outcomes_for_missing_outside_and_low_confidence():
    assert dm.derive_case(_case("B", None, -66.8, "Somewhere"), MUNICIPIOS)["outcome"] == "NO_COORDINATES"
    assert dm.derive_case(_case("C", 19.5, -66.8, "Offshore"), MUNICIPIOS)["outcome"] == "OUTSIDE_MUNICIPIOS"
    low = dm.derive_case(_case("D", 18.2, -66.2, "Bayamon", location_confidence=0.4), MUNICIPIOS)
    assert low["outcome"] == "DERIVED_LOW_CONFIDENCE"


def test_region_label_is_not_a_municipio_but_a_real_name_can_conflict():
    region = dm.derive_case(_case("E", 18.2, -66.8, "Añasco", municipality="west"), MUNICIPIOS)
    assert region["existing_class"] == "NON_MUNICIPIO_LABEL"
    conflict = dm.derive_case(_case("F", 18.2, -66.8, "Añasco", municipality="Bayamón"), MUNICIPIOS)
    assert conflict["outcome"] == "CONFLICTS_WITH_EXISTING"


def test_generic_location_names():
    for name in ("Puerto Rico (unspecified)", "North coast (unspecified)", "Island-wide", "Puerto Rico", None):
        assert dm.is_generic_location(name), name
    for name in ("Ramey AFB", "Barrio Hatillo, Añasco", "El Yunque"):
        assert not dm.is_generic_location(name), name


def test_review_classes(tmp_path):
    master = tmp_path / "master.jsonl"
    cases = [
        _case("agree", 18.2, -66.8, "Añasco"),
        _case("generic", 18.3, -66.3, "Interior (unspecified)"),
        # Same point as the generic case: a regional default, even though the name is specific.
        _case("default_point", 18.3, -66.3, "Miramar"),
        _case("disagree", 18.2, -66.2, "Plaza, Añasco"),
        _case("review", 18.2, -66.7, "Ramey AFB"),
        _case("none", None, None, "Unknown"),
    ]
    master.write_text("".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    geo = tmp_path / "municipios.geojson"
    geo.write_text(json.dumps({"features": [
        {"properties": {"name": m["name"], "geoid": m["geoid"]}, "geometry": m["geometry"]} for m in MUNICIPIOS
    ]}), encoding="utf-8")

    report = dm.build_report(master, geo)
    classes = {row["case_id"]: row["review_class"] for row in report["cases"]}
    assert classes == {
        "agree": "AGREES_WITH_LOCATION_NAME",
        "generic": "GENERIC_LOCATION_DO_NOT_APPLY",
        "default_point": "GENERIC_LOCATION_DO_NOT_APPLY",
        "disagree": "NAME_DISAGREES_WITH_POLYGON",
        "review": "NEEDS_REVIEW",
        "none": "NOT_DERIVED",
    }
    disagree = next(r for r in report["cases"] if r["case_id"] == "disagree")
    assert disagree["other_municipios_named"] == ["Añasco"]
    assert report["state"] == "CANDIDATE_NOT_SOURCE_EVIDENCE"
    assert report["summary"]["cases"] == 6


def test_main_writes_report_and_leaves_master_alone(tmp_path):
    before = dm.MASTER.read_bytes()
    out = tmp_path / "report.json"
    assert dm.main(["--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["summary"]["cases"] == len(report["cases"]) >= 470
    assert report["inputs"]["municipio_count"] == 78
    assert dm.MASTER.read_bytes() == before
