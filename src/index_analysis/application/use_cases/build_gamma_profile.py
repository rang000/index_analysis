from __future__ import annotations

import pandas as pd

from index_analysis.domain.gamma import black_scholes_gamma


def build_gamma_profile(
    option_data: pd.DataFrame,
    spot: float,
    range_pct: float,
    steps: int,
    contract_size: int,
    risk_free_rate: float,
) -> pd.DataFrame:
    if option_data.empty or pd.isna(spot):
        return pd.DataFrame()

    low = spot * (1 - range_pct / 100)
    high = spot * (1 + range_pct / 100)
    if steps < 5:
        steps = 5

    spot_levels = [low + (high - low) * index / (steps - 1) for index in range(steps)]
    rows = []
    compact = option_data[["optionType", "strike", "openInterest", "impliedVolatility", "daysToExpiry"]].copy()
    compact["timeToExpiry"] = compact["daysToExpiry"] / 365

    for level in spot_levels:
        total_gamma = 0.0
        for row in compact.itertuples(index=False):
            gamma = black_scholes_gamma(
                level,
                float(row.strike),
                float(row.impliedVolatility),
                float(row.timeToExpiry),
                risk_free_rate,
            )
            sign = 1 if row.optionType == "call" else -1
            total_gamma += sign * gamma * float(row.openInterest) * contract_size * level * level * 0.01
        rows.append({"SpotLevel": level, "GammaExposureBn": total_gamma / 1_000_000_000})

    return pd.DataFrame(rows)
