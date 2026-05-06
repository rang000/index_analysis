import pandas as pd

from index_analysis.application.use_cases.build_gamma_profile import build_gamma_profile


def test_build_gamma_profile_returns_profile_rows():
    option_data = pd.DataFrame(
        {
            "optionType": ["call", "put"],
            "strike": [100, 100],
            "openInterest": [1000, 500],
            "impliedVolatility": [0.2, 0.2],
            "daysToExpiry": [30, 30],
        }
    )

    result = build_gamma_profile(
        option_data=option_data,
        spot=100,
        range_pct=10,
        steps=11,
        contract_size=100,
        risk_free_rate=0.04,
    )

    assert len(result) == 11
    assert list(result.columns) == ["SpotLevel", "GammaExposureBn"]


def test_build_gamma_profile_uses_minimum_steps():
    option_data = pd.DataFrame(
        {
            "optionType": ["call"],
            "strike": [100],
            "openInterest": [1000],
            "impliedVolatility": [0.2],
            "daysToExpiry": [30],
        }
    )

    result = build_gamma_profile(
        option_data=option_data,
        spot=100,
        range_pct=10,
        steps=3,
        contract_size=100,
        risk_free_rate=0.04,
    )

    assert len(result) == 5
