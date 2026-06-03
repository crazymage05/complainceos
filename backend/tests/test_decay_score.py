import pytest

from engines.decay_score import (OVERDUE_SCORE_CEILING, compute_decay_score,
                                 compute_penalty_exposure, score_to_urgency)


class TestComputeDecayScore:
    def test_returns_zero_when_total_days_invalid(self):
        assert compute_decay_score(10, 0, 1, 1, 1.0) == 0.0
        assert compute_decay_score(10, -1, 1, 1, 1.0) == 0.0

    def test_returns_max_when_full_period_remaining_and_clean_record(self):
        score = compute_decay_score(
            days_remaining=30, total_days_allowed=30,
            complexity_weight=1.0, penalty_severity_multiplier=1.0,
            historical_on_time_rate=1.0,
        )
        assert score == 100.0

    def test_decays_proportionally_with_time_consumed(self):
        full = compute_decay_score(30, 30, 1.0, 1.0, 1.0)
        half = compute_decay_score(15, 30, 1.0, 1.0, 1.0)
        near = compute_decay_score(3, 30, 1.0, 1.0, 1.0)
        assert full > half > near > 0

    def test_overdue_returns_zero_when_no_penalty_data(self):
        assert compute_decay_score(-5, 30, 1.0, 1.0, 1.0) == 0.0

    def test_overdue_compounds_with_accrued_penalty(self):
        """1 day overdue should score higher (less critical) than 10 days."""
        day1 = compute_decay_score(
            days_remaining=-1, total_days_allowed=30,
            complexity_weight=1.0, penalty_severity_multiplier=1.0,
            historical_on_time_rate=1.0,
            base_penalty_inr=500, per_day_late_inr=50,
        )
        day10 = compute_decay_score(
            days_remaining=-10, total_days_allowed=30,
            complexity_weight=1.0, penalty_severity_multiplier=1.0,
            historical_on_time_rate=1.0,
            base_penalty_inr=500, per_day_late_inr=50,
        )
        assert OVERDUE_SCORE_CEILING >= day1 > day10 >= 0

    def test_personal_history_lowers_complexity_after_clean_runs(self):
        no_history = compute_decay_score(15, 30, 3.0, 1.0, 1.0)
        clean = compute_decay_score(
            15, 30, 3.0, 1.0, 1.0,
            times_filed_on_time=5, times_filed_late=0,
        )
        # A clean filer should see a higher (less urgent) score
        assert clean > no_history

    def test_repeated_late_filings_drag_score_down(self):
        no_history = compute_decay_score(15, 30, 1.0, 2.0, 0.5)
        repeat_late = compute_decay_score(
            15, 30, 1.0, 2.0, 0.5,
            times_filed_on_time=0, times_filed_late=4,
        )
        assert repeat_late < no_history


class TestComputePenaltyExposure:
    def test_zero_until_overdue(self):
        assert compute_penalty_exposure(5, 1000, 100, 50000) == 0.0
        assert compute_penalty_exposure(0, 1000, 100, 50000) == 0.0

    def test_accrues_per_day(self):
        assert compute_penalty_exposure(-1, 1000, 100, 50000) == 1100.0
        assert compute_penalty_exposure(-10, 1000, 100, 50000) == 2000.0

    def test_caps_at_max_penalty(self):
        result = compute_penalty_exposure(-1000, 1000, 100, 50000)
        assert result == 50000.0


class TestScoreToUrgency:
    @pytest.mark.parametrize("score,expected", [
        (0, "red"), (15, "red"), (19.99, "red"),
        (20, "amber"), (35, "amber"), (39.99, "amber"),
        (40, "green"), (80, "green"), (100, "green"),
    ])
    def test_banding(self, score, expected):
        assert score_to_urgency(score) == expected
