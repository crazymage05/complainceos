from engines.penalty_predictor import (LARGE_SIZE_MULTIPLIER,
                                       MID_SIZE_MULTIPLIER,
                                       SMALL_SIZE_MULTIPLIER,
                                       _entity_size_multiplier,
                                       _repeat_offender_factor,
                                       _turnover_multiplier, predict_penalty)


def test_size_multiplier_bands():
    assert _entity_size_multiplier(0) == SMALL_SIZE_MULTIPLIER
    assert _entity_size_multiplier(9) == SMALL_SIZE_MULTIPLIER
    assert _entity_size_multiplier(10) == MID_SIZE_MULTIPLIER
    assert _entity_size_multiplier(49) == MID_SIZE_MULTIPLIER
    assert _entity_size_multiplier(50) == LARGE_SIZE_MULTIPLIER
    assert _entity_size_multiplier(500) == LARGE_SIZE_MULTIPLIER


def test_turnover_multiplier_grows_with_band():
    micro = _turnover_multiplier(1_000_000)
    mid = _turnover_multiplier(50_000_000)
    large = _turnover_multiplier(500_000_000)
    enterprise = _turnover_multiplier(5_000_000_000)
    assert micro <= mid <= large <= enterprise


def test_repeat_offender_caps_at_three():
    assert _repeat_offender_factor(0) == 1.0
    assert _repeat_offender_factor(1) == 1.25
    assert _repeat_offender_factor(2) == 1.5
    # Anything beyond should not exceed the cap
    assert _repeat_offender_factor(10) == 1.5


def test_predict_penalty_returns_zero_when_not_overdue():
    p = predict_penalty(
        base_penalty_inr=1000, per_day_late_inr=100, max_penalty_inr=50000,
        employee_count=5, annual_turnover_inr=1_000_000,
        projected_days_late=0, times_missed_before=0,
    )
    assert p == 0.0


def test_predict_penalty_uses_turnover_band():
    """The turnover multiplier should actually move the output now."""
    small = predict_penalty(
        base_penalty_inr=1000, per_day_late_inr=100, max_penalty_inr=10_000_000,
        employee_count=5, annual_turnover_inr=1_000_000,
        projected_days_late=5, times_missed_before=0,
    )
    large = predict_penalty(
        base_penalty_inr=1000, per_day_late_inr=100, max_penalty_inr=10_000_000,
        employee_count=5, annual_turnover_inr=5_000_000_000,
        projected_days_late=5, times_missed_before=0,
    )
    assert large > small


def test_predict_penalty_caps_at_max():
    p = predict_penalty(
        base_penalty_inr=1000, per_day_late_inr=10000, max_penalty_inr=5000,
        employee_count=100, annual_turnover_inr=5_000_000_000,
        projected_days_late=365, times_missed_before=5,
    )
    assert p == 5000.0


def test_repeat_offender_inflates_predicted_amount():
    clean = predict_penalty(
        base_penalty_inr=1000, per_day_late_inr=100, max_penalty_inr=100_000,
        employee_count=5, annual_turnover_inr=1_000_000,
        projected_days_late=10, times_missed_before=0,
    )
    repeat = predict_penalty(
        base_penalty_inr=1000, per_day_late_inr=100, max_penalty_inr=100_000,
        employee_count=5, annual_turnover_inr=1_000_000,
        projected_days_late=10, times_missed_before=3,
    )
    assert repeat > clean
