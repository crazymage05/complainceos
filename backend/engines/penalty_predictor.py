from typing import Optional

def predict_penalty(
    base_penalty_inr: float,
    per_day_late_inr: float,
    max_penalty_inr: float,
    employee_count: int,
    annual_turnover_inr: float,
    projected_days_late: int,
    times_missed_before: int,
) -> float:
    """
    Penalty Prediction Engine — Patent Claim 4.
    Entity-specific penalty calculation.
    """
    size_multiplier = _entity_size_multiplier(employee_count, annual_turnover_inr)
    days_multiplier = _days_overdue_multiplier(projected_days_late, per_day_late_inr, base_penalty_inr)
    repeat_factor = _repeat_offender_factor(times_missed_before)

    # TODO: PATENT-PENDING — multiplier calibration values omitted
    predicted = base_penalty_inr * size_multiplier * days_multiplier * repeat_factor
    return round(min(predicted, max_penalty_inr), 2)


def _entity_size_multiplier(employee_count: int, turnover: float) -> float:
    # TODO: PATENT-PENDING — exact bracket thresholds omitted
    if employee_count < 10:
        return 0.5
    elif employee_count < 50:
        return 1.0
    return 1.5


def _days_overdue_multiplier(days_late: int, per_day: float, base: float) -> float:
    if days_late <= 0:
        return 0.0
    if base <= 0:
        return 1.0
    extra = per_day * days_late
    return 1.0 + (extra / base)


def _repeat_offender_factor(times_missed: int) -> float:
    # TODO: PATENT-PENDING — recidivism curve omitted
    if times_missed == 0:
        return 1.0
    elif times_missed == 1:
        return 1.25
    return 1.5
