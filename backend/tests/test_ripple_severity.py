from engines.ripple_detector import (HIGH_DIRECT, HIGH_TOTAL, MEDIUM_DIRECT,
                                     MEDIUM_TOTAL, _compute_severity)


def _stub(n):
    return [{"_id": str(i), "name": f"r{i}", "category": "x"} for i in range(n)]


def test_no_impacts_is_low():
    assert _compute_severity([], []) == "low"


def test_total_threshold_promotes_to_high():
    assert _compute_severity(_stub(0), _stub(HIGH_TOTAL)) == "high"


def test_direct_threshold_promotes_to_high():
    assert _compute_severity(_stub(HIGH_DIRECT), _stub(0)) == "high"


def test_medium_band():
    assert _compute_severity(_stub(MEDIUM_DIRECT), _stub(0)) == "medium"
    assert _compute_severity(_stub(0), _stub(MEDIUM_TOTAL)) == "medium"


def test_low_band_below_medium_threshold():
    direct_count = MEDIUM_DIRECT - 1 if MEDIUM_DIRECT > 0 else 0
    total_count = MEDIUM_TOTAL - 1 if MEDIUM_TOTAL > 0 else 0
    assert _compute_severity(_stub(direct_count), _stub(total_count - direct_count)) == "low"
