from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st


@dataclass(frozen=True)
class MarketInputs:
    index_name: str
    ticker_source: str
    custom_ticker: str
    ticker: str
    refresh: bool


@dataclass(frozen=True)
class PainPointInputs:
    price_start: object
    price_end: object
    start_mode: str
    custom_start_dates: str


@dataclass(frozen=True)
class GammaInputs:
    show_gamma: bool
    option_ticker: str
    max_expiries: int
    range_pct: int
    steps: int


def render_market_sidebar(
    index_options: dict[str, str],
    start_date: str,
    end_date: str,
) -> MarketInputs:
    with st.sidebar:
        st.header("Market")
        index_name = st.selectbox("Index", options=list(index_options), index=0)
        ticker_source = st.radio("Ticker source", options=["Preset", "Custom"], horizontal=True)
        custom_ticker = st.text_input("Custom ticker", value=index_options[index_name])
        ticker = index_options[index_name] if ticker_source == "Preset" else custom_ticker.strip()
        st.caption(f"Data range: {start_date} - {end_date}")
        refresh = st.button("Reload data")

    return MarketInputs(
        index_name=index_name,
        ticker_source=ticker_source,
        custom_ticker=custom_ticker,
        ticker=ticker,
        refresh=refresh,
    )


def render_analysis_sidebar(
    min_date: object,
    max_date: object,
    default_pain_price_start: object,
    default_cohort_starts: list[pd.Timestamp],
    option_ticker_defaults: dict[str, str],
    index_name: str,
) -> tuple[PainPointInputs, GammaInputs]:
    with st.sidebar:
        st.header("Pain Point")
        pain_price_start = st.date_input(
            "Price start",
            value=default_pain_price_start,
            min_value=min_date,
            max_value=max_date,
        )
        pain_price_end = st.date_input(
            "Price end",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
        )
        pain_start_mode = st.radio(
            "Pain starts",
            options=["Quarter starts", "Custom dates"],
            horizontal=False,
        )
        default_cohort_text = "\n".join(date.strftime("%Y-%m-%d") for date in default_cohort_starts)
        custom_cohort_text = st.text_area(
            "Custom start dates",
            value=default_cohort_text,
            height=104,
            disabled=pain_start_mode == "Quarter starts",
            help="1行に1日、またはカンマ区切りで指定できます。例: 2025-01-02, 2025-03-15",
        )

        st.header("Gamma Exposure")
        show_gamma = st.checkbox("Show gamma exposure", value=False)
        default_option_ticker = option_ticker_defaults.get(index_name, "SPY")
        option_ticker = st.text_input(
            "Option ticker",
            value=default_option_ticker,
            help="Yahoo Financeでoption chainを取得できるティッカーを指定します。SPX指数そのものが取れない場合はSPYなどのETFを使います。",
        )
        max_expiries = st.slider("Expiries", min_value=1, max_value=12, value=6)
        gamma_range_pct = st.slider("Spot range +/- %", min_value=5, max_value=30, value=15)
        gamma_steps = st.slider("Spot steps", min_value=25, max_value=121, value=61, step=2)

    return (
        PainPointInputs(
            price_start=pain_price_start,
            price_end=pain_price_end,
            start_mode=pain_start_mode,
            custom_start_dates=custom_cohort_text,
        ),
        GammaInputs(
            show_gamma=show_gamma,
            option_ticker=option_ticker,
            max_expiries=max_expiries,
            range_pct=gamma_range_pct,
            steps=gamma_steps,
        ),
    )
