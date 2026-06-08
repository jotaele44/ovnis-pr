import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pytest  # noqa: E402


def _master_case(**overrides):
    """A fully-valid master case (passes core_validate, yields full streams)."""
    case = {
        "record_id": "PRUFON-0001",
        "record_type": "master",
        "case_id": "PRUFON-0001",
        "date_local": "2024-06-15",
        "location_name": "Cabo Rojo lighthouse",
        "description": "Bright disc hovering over the coast for about ten minutes.",
        "source_url": "https://example.com/report",
        "evidence_tier": "T2",
        "dedupe_status": "new",
        "review_action": "promote",
        "municipality": "Cabo Rojo",
        "source_family": "news_report",
        "source_citation": "El Vocero",
    }
    case.update(overrides)
    return case


@pytest.fixture
def master_case():
    return _master_case


@pytest.fixture
def now():
    return "2026-01-01T00:00:00Z"
