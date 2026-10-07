import pytest
from server.backend.main import as_float, feature_from_case, normalize_case


@pytest.mark.parametrize("value", ["nan", "inf", "-Infinity", "1e999", float("inf")])
def test_coordinates_reject_nonfinite(value):
    assert as_float(value) is None
    case = normalize_case({"latitude": str(value), "longitude": "-66", "record_id": "case-1"})
    assert case["location"]["lat"] is None
    assert feature_from_case(case) is None
