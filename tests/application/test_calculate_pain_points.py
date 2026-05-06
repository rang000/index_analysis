import pandas as pd

from index_analysis.application.use_cases.calculate_pain_points import calculate_pain_points


def make_price_data() -> pd.DataFrame:
    close = pd.Series(range(100, 500), dtype=float)
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=len(close), freq="B"),
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Adj Close": close,
            "Volume": [1000] * len(close),
        }
    )


def test_calculate_pain_points_builds_window_and_cohorts():
    data = make_price_data()

    window, pain_data = calculate_pain_points(
        data=data,
        price_start=pd.Timestamp("2024-03-01"),
        price_end=pd.Timestamp("2024-12-31"),
        cohort_starts=[
            pd.Timestamp("2024-04-01"),
            pd.Timestamp("2024-07-01"),
        ],
        trend_lookbacks=(20, 60, 120, 250),
        trend_vol_window=60,
        trend_signal_scale=1.5,
    )

    assert not window.empty
    assert window["Date"].min() >= pd.Timestamp("2024-03-01")
    assert window["Date"].max() <= pd.Timestamp("2024-12-31")
    assert pain_data["Cohort"].nunique() == 2
    assert {
        "Date",
        "PainPoint",
        "PositionScore",
        "PositionAdd",
        "Cohort",
        "CohortDate",
        "Distance",
        "DistancePct",
        "Label",
    }.issubset(pain_data.columns)


def test_calculate_pain_points_returns_empty_for_invalid_window():
    data = make_price_data()

    window, pain_data = calculate_pain_points(
        data=data,
        price_start=pd.Timestamp("2024-12-31"),
        price_end=pd.Timestamp("2024-01-01"),
        cohort_starts=[pd.Timestamp("2024-04-01")],
        trend_lookbacks=(20, 60),
        trend_vol_window=60,
        trend_signal_scale=1.5,
    )

    assert window.empty
    assert pain_data.empty
