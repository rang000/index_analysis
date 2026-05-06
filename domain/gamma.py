from __future__ import annotations
from config.loader import load_settings

import math

settings = load_settings()

RISK_FREE_RATE = settings["risk_free_rate"]


def norm_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi)


def black_scholes_gamma(
    spot: float,
    strike: float,
    volatility: float,
    time_to_expiry: float,
    risk_free_rate: float = RISK_FREE_RATE,
) -> float:
    if spot <= 0 or strike <= 0 or volatility <= 0 or time_to_expiry <= 0:
        return 0.0

    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility * volatility) * time_to_expiry
    ) / (volatility * math.sqrt(time_to_expiry))

    return norm_pdf(d1) / (spot * volatility * math.sqrt(time_to_expiry))