"""Additive evidence_state declarations (thehub-pr FEDERATION_EPISTEMIC_STATE_CONTRACT_V1).

Positive: every exported row declares a schema-valid evidence_state, case
records are CURATED, and date precision is reported at the source's
resolution. Negative: OVNIS never declares a geometry precision it cannot
support, never invents a time, and never declares an absence.
"""

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from federation_export import EVIDENCE_STATE_CONTRACT, build_streams

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "schemas" / "federation_epistemic_state.v1.schema.json"
# sha256 of thehub-pr schemas/federation/epistemic_state.v1.schema.json (CANDIDATE).
HUB_CANDIDATE_SHA256 = "c31794807d47f00e9ffeb394cf9ddd5d093613dabcf22d4fd81d4a416bade088"
NOW = "2026-01-01T00:00:00Z"


def _validator():
    schema = json.loads(VENDORED.read_text())
    wrapper = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/producer_declaration"}
    return jsonschema.Draft202012Validator(wrapper)


def _rows(cases):
    streams = build_streams(cases, NOW)
    return [(stream, row) for stream, rows in streams.items() for row in rows]


def _observation(master_case, **overrides):
    streams = build_streams([master_case(**overrides)], NOW)
    return streams["observations"][0]


def test_vendored_contract_is_byte_identical_to_the_hub_candidate():
    assert hashlib.sha256(VENDORED.read_bytes()).hexdigest() == HUB_CANDIDATE_SHA256
    assert json.loads(VENDORED.read_text())["$id"] == "urn:prii:federation:epistemic_state:v1"


def test_every_row_declares_a_valid_evidence_state(master_case):
    validator = _validator()
    rows = _rows([master_case(), master_case(record_id="PRUFON-0002", case_id="PRUFON-0002", date_local="1974")])
    assert {stream for stream, _ in rows} == {"sources", "entities", "relationships", "observations"}
    for stream, row in rows:
        declaration = row["evidence_state"]
        assert declaration["contract"] == EVIDENCE_STATE_CONTRACT
        assert declaration["epistemic_class"] == "CURATED"
        assert declaration["data_stage"] == "CANONICAL"
        assert list(validator.iter_errors(declaration)) == [], (stream, declaration)


@pytest.mark.parametrize(
    "date_local, time_local, expected",
    [
        ("1974", None, "YEAR_ONLY"),
        ("1974-03", None, "MONTH_YEAR"),
        ("1974-03-12", None, "DATE_ONLY"),
        ("1974-03-12", "22:31", "EXACT_TIMESTAMP"),
    ],
)
def test_temporal_precision_matches_the_source_resolution(master_case, date_local, time_local, expected):
    observation = _observation(master_case, date_local=date_local, time_local=time_local)
    assert observation["evidence_state"]["temporal_precision"] == expected
    assert observation["evidence_state"]["observation_state"] == "OBSERVED_PRESENT"


def test_year_only_case_is_never_declared_at_day_or_time_resolution(master_case):
    observation = _observation(master_case, date_local="1929", time_local=None)
    assert observation["evidence_state"]["temporal_precision"] not in {"DATE_ONLY", "EXACT_TIMESTAMP"}
    # The Hub-required timestamp is floored, but the declaration keeps the truth.
    assert observation["observed_at"].startswith("1929-01-01T")


def test_no_geometry_precision_or_absence_is_ever_declared(master_case):
    cases = [
        master_case(latitude=18.4655, longitude=-66.1057),
        master_case(record_id="PRUFON-0003", case_id="PRUFON-0003", latitude=18.4655, longitude=-66.1057),
        master_case(record_id="PRUFON-0004", case_id="PRUFON-0004", municipality=None),
    ]
    for _, row in _rows(cases):
        declaration = row["evidence_state"]
        assert "geometry_precision" not in declaration
        assert "coordinate_method" not in declaration
        assert declaration.get("observation_state") != "OBSERVED_ABSENT"
