import json

from federation_export import build_streams, write_package


def _types(streams):
    return {e["entity_type"] for e in streams["entities"]}


def _rel_types(streams):
    return {r["relationship_type"] for r in streams["relationships"]}


def test_streams_have_four_keys(master_case, now):
    s = build_streams([master_case()], now)
    assert set(s) == {"sources", "entities", "relationships", "observations"}


def test_master_becomes_uap_case_entity(master_case, now):
    s = build_streams([master_case()], now)
    cases = [e for e in s["entities"] if e["entity_type"] == "uap_case"]
    assert len(cases) == 1
    assert cases[0]["name"] == "Cabo Rojo lighthouse"


def test_entity_and_relationship_types(master_case, now):
    s = build_streams([master_case()], now)
    assert _types(s) == {"uap_case", "municipality", "source_document"}
    assert _rel_types(s) == {"located_in", "reported_by"}


def test_id_prefixes(master_case, now):
    s = build_streams([master_case()], now)
    assert all(e["entity_id"].startswith("ent_") for e in s["entities"])
    assert all(r["source_id"].startswith("src_") for r in s["sources"])
    assert all(r["relationship_id"].startswith("rel_") for r in s["relationships"])
    assert all(o["observation_id"].startswith("obs_") for o in s["observations"])


def test_observation_fields(master_case, now):
    s = build_streams([master_case()], now)
    assert len(s["observations"]) == 1
    obs = s["observations"][0]
    assert obs["observation_id"].startswith("obs_")
    assert obs["entity_id"].startswith("ent_")
    assert obs["source_id"].startswith("src_")
    assert obs["evidence_tier"] == "T2"
    assert obs["date_local"] == "2024-06-15"


def test_non_master_records_skipped(master_case, now):
    s = build_streams([master_case(record_type="candidate")], now)
    assert s["entities"] == [] and s["sources"] == [] and s["relationships"] == [] and s["observations"] == []


def test_confidence_tier_mapping(master_case, now):
    for tier, score in [("T1", 0.9), ("T2", 0.7), ("T3", 0.5), ("T4", 0.3)]:
        s = build_streams([master_case(evidence_tier=tier)], now)
        case = next(e for e in s["entities"] if e["entity_type"] == "uap_case")
        assert case["confidence"] == score


def test_synthetic_flag_from_placeholder(master_case, now):
    placeholder = build_streams([master_case(source_family="placeholder")], now)
    assert all(r["synthetic"] for stream in placeholder.values() for r in stream)
    real = build_streams([master_case(source_family="news_report")], now)
    assert not any(r["synthetic"] for stream in real.values() for r in stream)


def test_municipality_dedup(master_case, now):
    a = master_case(record_id="PRUFON-1", case_id="PRUFON-1", municipality="Ponce")
    b = master_case(record_id="PRUFON-2", case_id="PRUFON-2", municipality="Ponce")
    s = build_streams([a, b], now)
    munis = [e for e in s["entities"] if e["entity_type"] == "municipality"]
    assert len(munis) == 1


def test_no_municipality_means_no_located_in(master_case, now):
    case = master_case()
    case.pop("municipality")
    s = build_streams([case], now)
    assert "municipality" not in _types(s)
    assert _rel_types(s) == {"reported_by"}


def test_duplicate_of_requires_dedupe_status_duplicate(master_case, now):
    dup = master_case(record_id="PRUFON-3", case_id="PRUFON-3",
                      matched_case_id="PRUFON-0001", dedupe_status="duplicate")
    assert "duplicate_of" in _rel_types(build_streams([dup], now))

    # matched_case_id present but dedupe_status != duplicate -> no edge
    nodup = master_case(record_id="PRUFON-4", case_id="PRUFON-4",
                        matched_case_id="PRUFON-0001", dedupe_status="new")
    assert "duplicate_of" not in _rel_types(build_streams([nodup], now))


def test_deterministic_ids(master_case, now):
    a = build_streams([master_case()], now)
    b = build_streams([master_case()], now)
    assert [e["entity_id"] for e in a["entities"]] == [e["entity_id"] for e in b["entities"]]


def test_write_package_manifest(master_case, now, tmp_path):
    s = build_streams([master_case()], now)
    manifest_path = write_package(s, tmp_path, "test", now)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["package_id"].startswith("pkg_")
    assert manifest["producer"] == "ovnis-pr"
    assert manifest["mode"] == "test"
    assert {f["stream"] for f in manifest["files"]} == {"sources", "entities", "relationships", "observations"}
    # per-file sha256 + record_count present
    for f in manifest["files"]:
        assert f["sha256"] and f["record_count"] >= 1
