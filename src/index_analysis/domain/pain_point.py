from __future__ import annotations

import pandas as pd


def add_trend_position(
    data: pd.DataFrame,
    lookbacks: tuple[int, ...],
    vol_window: int,
    signal_scale: float,
) -> pd.DataFrame:
    result = data.sort_values("Date").copy()
    close = result["Close"].astype(float)
    returns = close.pct_change()
    vol = returns.rolling(vol_window, min_periods=20).std()

    signals = []
    for lookback in lookbacks:
        momentum = close.pct_change(lookback)
        zscore = momentum / (vol * lookback**0.5)
        signals.append((zscore / signal_scale).clip(-1, 1))

    signal_frame = pd.concat(signals, axis=1)
    result["TrendPosition"] = signal_frame.mean(axis=1).clip(-1, 1).fillna(0)
    return result


def weighted_pain_point(cohort: pd.DataFrame) -> pd.DataFrame:
    position = cohort["TrendPosition"].clip(lower=0).fillna(0)
    additions = position.diff().clip(lower=0).fillna(position)

    if additions.sum() == 0 and position.iloc[0] > 0:
        additions.iloc[0] = position.iloc[0]

    weighted_cost = (additions * cohort["Close"]).cumsum()
    cumulative_additions = additions.cumsum()
    pain_point = weighted_cost / cumulative_additions.replace(0, pd.NA)
    fallback = cohort["Close"].expanding().mean()

    cohort = cohort.copy()
    cohort["PainPoint"] = pain_point.ffill().fillna(fallback)
    cohort["PositionScore"] = cohort["TrendPosition"]
    cohort["PositionAdd"] = additions
    return cohort
