import math

from logging_config import get_logger

log = get_logger(__name__)


# Tuning constants — calibrated against MSME filing data.
OVERDUE_SCORE_CEILING = 15.0           # overdue items score in 0..ceiling
OVERDUE_PENALTY_SATURATION = 10.0      # accrued / (base * this) = full exposure
COMPLEXITY_LEARNING_RATE = 0.15        # each on-time filing reduces complexity
COMPLEXITY_LEARNING_CAP = 5            # learning saturates after 5 on-time filings
LATE_PENALTY_GROWTH = 0.20             # each late filing inflates penalty severity
LATE_PENALTY_CAP = 4                   # severity growth saturates after 4 lates
HISTORICAL_BLEND_WEIGHT = 0.5          # 50/50 blend of historical + personal rate

# How aggressively complexity / penalty modulate the time-based score.
# Old formula used (1/complexity × 1/penalty), capping a c=4 + p=3 item at
# 100/(4×3) = 8.3 — every high-stakes filing showed red regardless of how
# much time was left. New formula subtracts a few points instead of dividing,
# so c/p act as modifiers, not ceilings.
COMPLEXITY_PENALTY_SHIFT_K = 0.12      # weight of the log-shift


def compute_decay_score(
    days_remaining: float,
    total_days_allowed: float,
    complexity_weight: float,
    penalty_severity_multiplier: float,
    historical_on_time_rate: float,
    times_filed_on_time: int = 0,
    times_filed_late: int = 0,
    base_penalty_inr: float = 0.0,
    per_day_late_inr: float = 0.0,
) -> float:
    """
    Composite freshness score: higher = safer, lower = more urgent.

    Personalisation layer adjusts complexity and penalty weights from this
    business's filing track record. Overdue obligations reflect actual daily
    penalty accrual instead of flat-zeroing to keep the dashboard meaningful.
    """
    if total_days_allowed <= 0:
        return 0.0

    total_filings = times_filed_on_time + times_filed_late
    if total_filings > 0:
        personal_on_time_rate = times_filed_on_time / total_filings
        complexity_adj = complexity_weight * (
            1.0 - COMPLEXITY_LEARNING_RATE * min(times_filed_on_time, COMPLEXITY_LEARNING_CAP)
        )
        complexity_adj = max(complexity_adj, 1.0)
        penalty_adj = penalty_severity_multiplier * (
            1.0 + LATE_PENALTY_GROWTH * min(times_filed_late, LATE_PENALTY_CAP)
        )
        blended_rate = (
            HISTORICAL_BLEND_WEIGHT * historical_on_time_rate
            + (1.0 - HISTORICAL_BLEND_WEIGHT) * personal_on_time_rate
        )
    else:
        complexity_adj = complexity_weight
        penalty_adj = penalty_severity_multiplier
        blended_rate = historical_on_time_rate

    # Overdue compounding: GSTR-3B 10 days overdue (₹5,000 accrued) scores
    # lower than one 1 day overdue (₹500 accrued). Without this, all overdue = 0.
    if days_remaining < 0 and per_day_late_inr > 0 and base_penalty_inr > 0:
        days_overdue = abs(days_remaining)
        accrued_penalty = base_penalty_inr + per_day_late_inr * days_overdue
        saturation = base_penalty_inr * OVERDUE_PENALTY_SATURATION
        overdue_severity = min(accrued_penalty / saturation, 1.0)
        return round(max(0.0, OVERDUE_SCORE_CEILING * (1.0 - overdue_severity)), 2)

    if days_remaining < 0:
        return 0.0

    time_ratio = max(days_remaining / total_days_allowed, 0.0)

    # Time gives the base score; complexity & penalty severity SHIFT it down
    # (never below zero) instead of dividing it. This way a complex, high-
    # penalty obligation with 100% time remaining still reads as "green",
    # but a complex obligation with 30% time looks more urgent than a simple
    # one with the same time remaining.
    base = time_ratio * max(min(blended_rate, 1.0), 0.0) * 100.0
    shift_complexity = math.log10(max(complexity_adj, 1.0)) * 100.0 * COMPLEXITY_PENALTY_SHIFT_K
    shift_penalty = math.log10(max(penalty_adj, 1.0)) * 100.0 * COMPLEXITY_PENALTY_SHIFT_K
    raw = base - shift_complexity - shift_penalty

    return round(max(0.0, min(100.0, raw)), 2)


def compute_penalty_exposure(
    days_remaining: float,
    base_penalty_inr: float,
    per_day_late_inr: float,
    max_penalty_inr: float,
) -> float:
    """Current rupee exposure if not filed today. 0 until overdue. Capped at max."""
    if days_remaining >= 0 or per_day_late_inr <= 0:
        return 0.0
    days_overdue = abs(days_remaining)
    accrued = base_penalty_inr + per_day_late_inr * days_overdue
    return round(min(accrued, max_penalty_inr), 2)


# Urgency band thresholds — also referenced from the frontend palette.
URGENCY_RED_BELOW = 20.0
URGENCY_AMBER_BELOW = 40.0


def score_to_urgency(score: float) -> str:
    if score < URGENCY_RED_BELOW:
        return "red"
    if score < URGENCY_AMBER_BELOW:
        return "amber"
    return "green"
