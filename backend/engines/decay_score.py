from typing import Optional
import math


def compute_decay_score(
    days_remaining: float,
    total_days_allowed: float,
    complexity_weight: float,
    penalty_severity_multiplier: float,
    historical_on_time_rate: float,
    # Personalisation inputs — defaults preserve existing behaviour
    times_filed_on_time: int = 0,
    times_filed_late: int = 0,
    base_penalty_inr: float = 0.0,
    per_day_late_inr: float = 0.0,
) -> float:
    """
    Regulatory Decay Score — Patent Claim 1.
    Composite freshness score: higher = safer, lower = more urgent.

    Personalisation layer: complexity_weight and penalty_severity are adjusted
    based on this specific business's filing track record for this obligation.
    Overdue compounding: when days_remaining < 0, the score reflects actual
    daily penalty accrual, not just a static zero.
    """
    if total_days_allowed <= 0:
        return 0.0

    # ── Personalised weight adjustment ───────────────────────────────────────
    # Each on-time filing reduces effective complexity (business has learned it).
    # Each late filing increases penalty severity (pattern of late = higher risk).
    total_filings = times_filed_on_time + times_filed_late
    if total_filings > 0:
        personal_on_time_rate = times_filed_on_time / total_filings
        # Complexity shrinks toward 1.0 as the business builds a clean record
        complexity_adj = complexity_weight * (1.0 - 0.15 * min(times_filed_on_time, 5))
        complexity_adj = max(complexity_adj, 1.0)
        # Penalty severity grows with each late filing (compound risk signal)
        penalty_adj = penalty_severity_multiplier * (1.0 + 0.20 * min(times_filed_late, 4))
        # Blend historical rate from DB with personal rate
        blended_rate = 0.5 * historical_on_time_rate + 0.5 * personal_on_time_rate
    else:
        complexity_adj = complexity_weight
        penalty_adj = penalty_severity_multiplier
        blended_rate = historical_on_time_rate

    # ── Overdue compounding ───────────────────────────────────────────────────
    # For overdue obligations: score decays further based on actual penalty accrual.
    # A GSTR-3B at day 10 overdue (₹500/day = ₹5,000 accrued) scores lower than
    # one at day 1 overdue (₹500 accrued). Without this, all overdue = 0.
    if days_remaining < 0 and per_day_late_inr > 0 and base_penalty_inr > 0:
        days_overdue = abs(days_remaining)
        accrued_penalty = base_penalty_inr + per_day_late_inr * days_overdue
        max_meaningful_penalty = base_penalty_inr * 10  # 10x base = fully exposed
        overdue_severity = min(accrued_penalty / max_meaningful_penalty, 1.0)
        # Score sits in 0–15 range for overdue, getting lower as penalty grows
        return round(max(0.0, 15.0 * (1.0 - overdue_severity)), 2)

    if days_remaining < 0:
        return 0.0

    time_ratio = max(days_remaining / total_days_allowed, 0.0)

    # TODO: PATENT-PENDING — exact weight constants omitted
    raw = (
        time_ratio
        * (1.0 / max(complexity_adj, 1.0))
        * (1.0 / max(penalty_adj, 1.0))
        * max(min(blended_rate, 1.0), 0.0)
        * 100.0
    )

    return round(max(0.0, min(100.0, raw)), 2)


def compute_penalty_exposure(
    days_remaining: float,
    base_penalty_inr: float,
    per_day_late_inr: float,
    max_penalty_inr: float,
) -> float:
    """
    Current rupee exposure if the obligation is not filed today.
    Returns 0 if not yet overdue. Caps at max_penalty_inr.
    Used to display the live ₹ exposure counter on the dashboard.
    """
    if days_remaining >= 0 or per_day_late_inr <= 0:
        return 0.0
    days_overdue = abs(days_remaining)
    accrued = base_penalty_inr + per_day_late_inr * days_overdue
    return round(min(accrued, max_penalty_inr), 2)


def score_to_urgency(score: float) -> str:
    if score < 20:
        return "red"
    elif score < 40:
        return "amber"
    return "green"
