"""Case identifier and narrative on federation export rows.

The Hub's timeline and case views read each case's own id and narrative from
the export. Positive: both are copied verbatim from the ledger onto the case
entity and its observation. Negative: a missing description or citation is
omitted, never replaced with a placeholder, and nothing else is invented.
"""

import json
from pathlib import Path

from federation_export import build_streams

REPO = Path(__file__).resolve().parents[1]
NOW = "2026-01-01T00:00:00Z"


def _case_rows(case):
    streams = build_streams([case], NOW)
    entity = next(e for e in streams["entities"] if e["entity_type"] == "uap_case")
    return entity, streams["observations"][0]


def test_case_id_and_narrative_are_copied_verbatim(master_case):
    case = master_case()
    entity, observation = _case_rows(case)
    assert entity["external_ids"] == {"ovnis_case_id": "PRUFON-0001"}
    assert entity["attributes"]["case_id"] == observation["attributes"]["case_id"] == "PRUFON-0001"
    assert entity["attributes"]["description"] == observation["attributes"]["description"] == case["description"]
    assert observation["attributes"]["source_citation"] == "El Vocero"
    assert "object_type" not in entity["attributes"]  # the fixture case has none
    assert entity["attributes"]["event_date"] == "2024-06-15"
    assert entity["attributes"]["evidence_tier"] == "T2"
    assert observation["entity_id"] == entity["entity_id"]


def test_missing_narrative_is_omitted_not_invented(master_case):
    entity, observation = _case_rows(master_case(description="  ", source_citation=None,
                                                 evidence_tier=None, object_type=None))
    for attributes in (entity["attributes"], observation["attributes"]):
        assert "description" not in attributes
        assert "source_citation" not in attributes
        assert None not in attributes.values() and "" not in attributes.values()
    assert entity["attributes"] == {"case_id": "PRUFON-0001", "event_date": "2024-06-15"}


def test_year_only_case_keeps_its_ledger_date(master_case):
    entity, _ = _case_rows(master_case(date_local="1967"))
    assert entity["attributes"]["event_date"] == "1967"


def test_every_ledger_case_exports_its_id_and_narrative():
    cases = [json.loads(line) for line in (REPO / "data/master/master_cases.jsonl").read_text().splitlines() if line.strip()]
    streams = build_streams(cases, NOW)
    by_id = {c["case_id"]: c for c in cases}
    entities = [e for e in streams["entities"] if e["entity_type"] == "uap_case"]
    assert len(entities) == len(cases)
    for entity in entities:
        case = by_id[entity["external_ids"]["ovnis_case_id"]]
        assert entity["attributes"].get("description") == (case["description"] or None)
    for observation in streams["observations"]:
        case = by_id[observation["attributes"]["case_id"]]
        assert observation["attributes"].get("description") == (case["description"] or None)
