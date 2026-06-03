from logging_config import get_logger

log = get_logger(__name__)


# ── Tuning constants ──────────────────────────────────────────────────────────
# Calibrated from observed MSME enforcement patterns (GST, EPF, FSSAI).

SMALL_EMPLOYEE_THRESHOLD = 10
MID_EMPLOYEE_THRESHOLD = 50
SMALL_SIZE_MULTIPLIER = 0.5
MID_SIZE_MULTIPLIER = 1.0
LARGE_SIZE_MULTIPLIER = 1.5

# Turnover-band uplift (₹ crore). Larger entities draw harsher enforcement.
TURNOVER_BANDS_INR = [
    (40_000_000, 1.0),     # < 4 cr
    (200_000_000, 1.15),   # < 20 cr
    (1_000_000_000, 1.3),  # < 100 cr
]
TURNOVER_LARGE_MULTIPLIER = 1.5

# Repeat-offender curve
REPEAT_MULTIPLIERS = {0: 1.0, 1: 1.25, 2: 1.5}
REPEAT_MAX_MULTIPLIER = 1.5


def predict_penalty(
    base_penalty_inr: float,
    per_day_late_inr: float,
    max_penalty_inr: float,
    employee_count: int,
    annual_turnover_inr: float,
    projected_days_late: int,
    times_missed_before: int,
) -> float:
    """Entity-specific penalty forecast in INR. Bounded by ``max_penalty_inr``."""
    size_multiplier = _entity_size_multiplier(employee_count)
    turnover_multiplier = _turnover_multiplier(annual_turnover_inr)
    days_multiplier = _days_overdue_multiplier(
        projected_days_late, per_day_late_inr, base_penalty_inr
    )
    repeat_factor = _repeat_offender_factor(times_missed_before)

    predicted = (
        base_penalty_inr
        * size_multiplier
        * turnover_multiplier
        * days_multiplier
        * repeat_factor
    )
    return round(min(predicted, max_penalty_inr), 2)


def _entity_size_multiplier(employee_count: int) -> float:
    if employee_count < SMALL_EMPLOYEE_THRESHOLD:
        return SMALL_SIZE_MULTIPLIER
    if employee_count < MID_EMPLOYEE_THRESHOLD:
        return MID_SIZE_MULTIPLIER
    return LARGE_SIZE_MULTIPLIER


def _turnover_multiplier(turnover_inr: float) -> float:
    for threshold, mult in TURNOVER_BANDS_INR:
        if turnover_inr < threshold:
            return mult
    return TURNOVER_LARGE_MULTIPLIER


def _days_overdue_multiplier(days_late: int, per_day: float, base: float) -> float:
    if days_late <= 0:
        return 0.0
    if base <= 0:
        return 1.0
    extra = per_day * days_late
    return 1.0 + (extra / base)


def _repeat_offender_factor(times_missed: int) -> float:
    return REPEAT_MULTIPLIERS.get(times_missed, REPEAT_MAX_MULTIPLIER)
