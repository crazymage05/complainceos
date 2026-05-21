from typing import Optional
import math

def compute_decay_score(
    days_remaining: float,
    total_days_allowed: float,
    complexity_weight: float,
    penalty_severity_multiplier: float,
    historical_on_time_rate: float,
) -> float:
    """
    Regulatory Decay Score — Patent Claim 1.
    Composite freshness score: higher = safer, lower = urgent.
    """
    if total_days_allowed <= 0:
        return 0.0

    time_ratio = max(days_remaining / total_days_allowed, 0.0)

    # TODO: PATENT-PENDING — exact weight constants omitted
    raw = (
        time_ratio
        * (1.0 / max(complexity_weight, 1.0))
        * (1.0 / max(penalty_severity_multiplier, 1.0))
        * max(min(historical_on_time_rate, 1.0), 0.0)
        * 100.0
    )

    return round(max(0.0, min(100.0, raw)), 2)


def score_to_urgency(score: float) -> str:
    if score < 20:
        return "red"
    elif score < 40:
        return "amber"
    return "green"
