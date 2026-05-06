from __future__ import annotations

import pandas as pd

from domain.pain_point import add_trend_position, weighted_pain_point


def clamp_date(
    value: pd.Timestamp,
    min_value: pd.Timestamp,
    max_value: pd.Timestamp,
) -> pd.Timestamp:
    return min(max(value, min_value), max_value)


def nearest_trading_date(
    data: pd.DataFrame,
    target: pd.Timestamp,
) -> pd.Timestamp | None:
    candidates = data[data["Date"] >= target]
    if candidates.empty:
        return None
    return candidates.iloc[0]["Date"]


def calculate_pain_points(
    data: pd.DataFrame,
    price_start: pd.Timestamp,
    price_end: pd.Timestamp,
    cohort_starts: list[pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = add_trend_position(data)

    price_start = clamp_date(price_start, data["Date"].min(), data["Date"].max())
    price_end = clamp_date(price_end, data["Date"].min(), data["Date"].max())

    if price_start > price_end:
        return pd.DataFrame(), pd.DataFrame()

    window = data[(data["Date"] >= price_start) & (data["Date"] <= price_end)].copy()
    if window.empty:
        return pd.DataFrame(), pd.DataFrame()

    cohort_dates: list[pd.Timestamp] = []

    for cohort_start in cohort_starts:
        if cohort_start > price_end:
            continue

        trading_date = nearest_trading_date(window, max(cohort_start, price_start))
        if trading_date is not None and trading_date not in cohort_dates:
            cohort_dates.append(trading_date)

    pain_frames = []

    for cohort_date in cohort_dates:
        cohort = window[window["Date"] >= cohort_date][
            ["Date", "Close", "TrendPosition"]
        ].copy()

        if cohort.empty:
            continue

        cohort = weighted_pain_point(cohort)
        cohort["Cohort"] = f"from {cohort_date.strftime('%b %Y')}"
        cohort["CohortDate"] = cohort_date

        pain_frames.append(
            cohort[
                [
                    "Date",
                    "PainPoint",
                    "PositionScore",
                    "PositionAdd",
                    "Cohort",
                    "CohortDate",
                ]
            ]
        )

    if not pain_frames:
        return window, pd.DataFrame()

    pain_data = pd.concat(pain_frames, ignore_index=True)

    latest_close = window.dropna(subset=["Close"]).iloc[-1]["Close"]
    latest_date = window.dropna(subset=["Close"]).iloc[-1]["Date"]

    labels = pain_data[pain_data["Date"] == latest_date].copy()
    labels["Distance"] = latest_close - labels["PainPoint"]
    labels["DistancePct"] = labels["Distance"] / labels["PainPoint"] * 100
    labels["Label"] = labels.apply(
        lambda row: (
            f"{row['Cohort']} "
            f"{row['PainPoint']:,.0f} "
            f"{row['DistancePct']:+.1f}%"
        ),
        axis=1,
    )

    return window, pain_data.merge(
        labels[["Cohort", "Distance", "DistancePct", "Label"]],
        on="Cohort",
        how="left",
    )