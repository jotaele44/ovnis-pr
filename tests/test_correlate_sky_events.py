from scripts.correlate_sky_events import build_ledger, calendar_overlap


def _case(case_id: str, date_local: str) -> dict:
    return {"case_id": case_id, "date_local": date_local}


def _event(event_id: str, start_utc: str) -> dict:
    return {
        "sky_event_id": event_id,
        "start_utc": start_utc,
        "source_url_canonical": f"https://example.test/{event_id}",
    }


def test_calendar_overlap_is_precision_aware_discovery_only() -> None:
    assert calendar_overlap("2025", "2025-02-18")
    assert calendar_overlap("2025-02", "2025-02-18")
    assert calendar_overlap("2025-02-18", "2025-02-18")
    assert not calendar_overlap("2025-01", "2025-02-18")
    assert not calendar_overlap(None, "2025-02-18")


def test_multiple_candidates_are_preserved_without_row_synthesis() -> None:
    cases = [_case("C1", "2025-02-18"), _case("C2", "2025-03-01")]
    events = [_event("E1", "2025-02-18T23:21:00Z"), _event("E2", "2025-02-18T23:30:00Z")]
    result = build_ledger(cases, events)
    assert result["candidate_edge_count"] == 2
    assert {edge["sky_event_id"] for edge in result["edges"]} == {"E1", "E2"}
    assert all(edge["case_id"] == "C1" for edge in result["edges"])
    assert all(edge["classification"] == "UNRESOLVED" for edge in result["edges"])


def test_case_arithmetic_closes_independently_of_edge_count() -> None:
    cases = [_case("C1", "2025-02-18"), _case("C2", "2025-03-01"), _case("C3", "2024")]
    events = [_event("E1", "2025-02-18T23:21:00Z"), _event("E2", "2025-02-18T23:30:00Z")]
    result = build_ledger(cases, events)
    d = result["case_disposition"]
    assert result["case_count"] == 3
    assert result["candidate_edge_count"] == 2
    assert d["UNRESOLVED"] == 1
    assert d["NO_ELIGIBLE_SKY_DATA"] == 2
    assert sum(d.values()) == result["case_count"]
    assert result["arithmetic_closed"] is True


def test_duplicate_case_ids_fail_closed() -> None:
    cases = [_case("C1", "2025-01-01"), _case("C1", "2025-01-02")]
    events = [_event("E1", "2025-01-01T00:00:00Z")]
    try:
        build_ledger(cases, events)
    except ValueError as exc:
        assert "duplicate case_id" in str(exc)
    else:
        raise AssertionError("duplicate case_id must fail closed")
