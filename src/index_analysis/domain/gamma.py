from __future__ import annotations

import math


def norm_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi)


def black_scholes_gamma(
    spot: float,
    strike: float,
    volatility: float,
    time_to_expiry: float,
    risk_free_rate: float,
) -> float:
    if spot <= 0 or strike <= 0 or volatility <= 0 or time_to_expiry <= 0:
        return 0.0

    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility * volatility) * time_to_expiry
    ) / (volatility * math.sqrt(time_to_expiry))

    return norm_pdf(d1) / (spot * volatility * math.sqrt(time_to_expiry))
