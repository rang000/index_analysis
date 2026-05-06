import pandas as pd

from index_analysis.domain.pain_point import add_trend_position, weighted_pain_point


def test_add_trend_position_adds_column():
    data = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=300),
            "Close": range(100, 400),
        }
    )

    result = add_trend_position(
        data,
        lookbacks=(20, 60, 120, 250),
        vol_window=60,
        signal_scale=1.5,
    )

    assert "TrendPosition" in result.columns
    assert result["TrendPosition"].between(-1, 1).all()


def test_weighted_pain_point_adds_pain_point_column():
    cohort = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=3),
            "Close": [100, 110, 120],
            "TrendPosition": [0.1, 0.3, 0.2],
        }
    )

    result = weighted_pain_point(cohort)

    assert "PainPoint" in result.columns
    assert "PositionAdd" in result.columns
