from __future__ import annotations

import pandas as pd
import streamlit as st

from index_analysis.application.ports.market_data_port import MarketDataPort
from index_analysis.application.ports.option_chain_port import OptionChainPort
from index_analysis.application.use_cases.build_gamma_profile import build_gamma_profile
from index_analysis.application.use_cases.calculate_pain_points import calculate_pain_points
from index_analysis.presentation.streamlit.charts import (
    gamma_profile_chart,
    pain_point_chart,
    price_chart,
    volume_chart,
)
from index_analysis.presentation.streamlit.selection_summary import (
    format_number,
    render_selection_summary,
    selected_column_values,
)
from index_analysis.presentation.streamlit.sidebar import render_analysis_sidebar, render_market_sidebar


@st.cache_data(show_spinner="Market data loading...")
def load_market_data(ticker: str, start: str, end: str, _client: MarketDataPort) -> pd.DataFrame:
    return _client.load_daily_prices(ticker, start, end)


@st.cache_data(show_spinner="Option chain loading...", ttl=60 * 30)
def load_option_chain(
    option_ticker: str,
    max_expiries: int,
    _client: OptionChainPort,
) -> tuple[pd.DataFrame, float]:
    return _client.load_option_chain(option_ticker, max_expiries)


def filter_by_date(data: pd.DataFrame, date_range: tuple[pd.Timestamp, pd.Timestamp]) -> pd.DataFrame:
    start, end = date_range
    return data[(data["Date"] >= pd.Timestamp(start)) & (data["Date"] <= pd.Timestamp(end))]


def clamp_date(value: pd.Timestamp, min_value: pd.Timestamp, max_value: pd.Timestamp) -> pd.Timestamp:
    return min(max(value, min_value), max_value)


def quarter_start(value: pd.Timestamp, quarter_months: int) -> pd.Timestamp:
    quarter_month = ((value.month - 1) // quarter_months) * quarter_months + 1
    return pd.Timestamp(year=value.year, month=quarter_month, day=1)


def latest_quarter_starts(end_date: pd.Timestamp, count: int, quarter_months: int) -> list[pd.Timestamp]:
    current = quarter_start(end_date, quarter_months)
    starts = []
    for _ in range(count):
        starts.append(current)
        current = current - pd.DateOffset(months=quarter_months)
    return list(reversed(starts))


def parse_date_list(value: str) -> list[pd.Timestamp]:
    dates = []
    for raw_item in value.replace("\n", ",").split(","):
        item = raw_item.strip()
        if not item:
            continue
        parsed = pd.to_datetime(item, errors="coerce")
        if pd.isna(parsed):
            continue
        dates.append(pd.Timestamp(parsed).normalize())
    return dates


def inject_terminal_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --terminal-bg: #050608;
            --panel-bg: #111419;
            --panel-border: #31363f;
            --amber: #f6b500;
            --green: #21d07a;
            --red: #ff4d4f;
            --muted: #a3aab8;
        }
        .stApp { background: var(--terminal-bg); color: #e6edf3; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
            background: #0b0d10;
            border-right: 1px solid var(--panel-border);
        }
        [data-testid="stSidebar"] * { color: #e6edf3; }
        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 1.5rem;
            max-width: 1500px;
        }
        .terminal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            padding: 7px 10px;
            background: linear-gradient(90deg, #11223b 0%, #6b1018 58%, #d22f3e 100%);
            border: 1px solid #586070;
            color: white;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 14px;
            line-height: 1.2;
        }
        .terminal-subheader {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 10px;
            border: 1px solid var(--panel-border);
            border-top: 0;
            background: #0b0d10;
            color: var(--amber);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
        }
        .market-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin: 10px 0 12px;
        }
        .quote-card {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 4px;
            padding: 10px 12px;
            min-height: 82px;
        }
        .quote-label {
            color: var(--muted);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            text-transform: uppercase;
        }
        .quote-value {
            color: var(--amber);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 25px;
            font-weight: 700;
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .quote-delta-pos { color: var(--green); }
        .quote-delta-neg { color: var(--red); }
        .quote-sub {
            color: #cbd5e1;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            margin-top: 2px;
        }
        .section-label {
            margin-top: 8px;
            padding: 4px 8px;
            background: #171a20;
            border: 1px solid var(--panel-border);
            color: var(--amber);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            font-weight: 700;
        }
        h1, h2, h3, label, .stMarkdown, .stCaption { color: #e6edf3; }
        .stDataFrame { border: 1px solid var(--panel-border); }
        .pain-note, .selection-summary {
            color: #cbd5e1;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            border: 1px solid var(--panel-border);
            background: #0b0d10;
            padding: 8px 10px;
            margin-top: 6px;
        }
        .summary-title {
            color: var(--amber);
            font-size: 12px;
            margin-bottom: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(100px, 1fr));
            gap: 6px;
        }
        .summary-grid div {
            border: 1px solid #252a33;
            background: #111419;
            padding: 6px 8px;
            min-width: 0;
        }
        .summary-grid span {
            display: block;
            color: var(--muted);
            font-size: 10px;
            line-height: 1.2;
            text-transform: uppercase;
        }
        .summary-grid strong {
            display: block;
            color: #e6edf3;
            font-size: 13px;
            line-height: 1.25;
            margin-top: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .summary-empty { color: #cbd5e1; font-size: 12px; }
        @media (max-width: 900px) {
            .market-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .quote-value { font-size: 20px; }
            .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def terminal_header(index_name: str, ticker: str, start: str, end: str) -> None:
    st.markdown(
        f"""
        <div class="terminal-header">
            <div>&lt;MARKET&gt; INDEX ANALYSIS</div>
            <div>{index_name} / {ticker}</div>
        </div>
        <div class="terminal-subheader">
            <span>Price and Volume Monitor</span>
            <span>{start} - {end}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def quote_strip(
    latest_close: float,
    latest_volume: float,
    latest_date: pd.Timestamp,
    change: float | None,
    change_pct: float | None,
    start_date: str,
    end_date: str,
) -> None:
    delta_class = "quote-delta-pos" if change is not None and change >= 0 else "quote-delta-neg"
    delta_text = "-" if change is None else f"{change:+,.2f} ({change_pct:+,.2f}%)"
    st.markdown(
        f"""
        <div class="market-strip">
            <div class="quote-card">
                <div class="quote-label">Last Close</div>
                <div class="quote-value">{format_number(latest_close)}</div>
                <div class="quote-sub {delta_class}">{delta_text}</div>
            </div>
            <div class="quote-card">
                <div class="quote-label">Volume</div>
                <div class="quote-value">{format_number(latest_volume, digits=0)}</div>
                <div class="quote-sub">daily traded volume</div>
            </div>
            <div class="quote-card">
                <div class="quote-label">Last Date</div>
                <div class="quote-value">{latest_date.strftime("%Y-%m-%d")}</div>
                <div class="quote-sub">latest observation</div>
            </div>
            <div class="quote-card">
                <div class="quote-label">Range</div>
                <div class="quote-value">{start_date}</div>
                <div class="quote-sub">to {end_date}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main(
    settings: dict,
    market_data_client: MarketDataPort,
    option_chain_client: OptionChainPort,
) -> None:
    st.set_page_config(page_title="Index Analysis Terminal", layout="wide")
    inject_terminal_style()

    index_options = settings["index_options"]
    start_date = settings["start_date"]
    end_date = settings["end_date"]
    market_inputs = render_market_sidebar(index_options, start_date, end_date)

    if market_inputs.refresh:
        load_market_data.clear()

    if not market_inputs.ticker:
        st.error("ティッカーを入力してください。")
        return

    display_name = market_inputs.index_name if market_inputs.ticker_source == "Preset" else "Custom"
    terminal_header(display_name, market_inputs.ticker, start_date, end_date)

    data = load_market_data(market_inputs.ticker, start_date, end_date, market_data_client)
    if data.empty:
        st.error("データを取得できませんでした。ティッカーまたはネットワーク接続を確認してください。")
        return

    min_date = data["Date"].min().date()
    max_date = data["Date"].max().date()
    pain_window_years = settings["pain_window_years"]
    quarter_months = settings["quarter_months"]
    pain_cohort_count = settings["pain_cohort_count"]
    default_pain_price_start = clamp_date(
        data["Date"].max() - pd.DateOffset(years=pain_window_years),
        data["Date"].min(),
        data["Date"].max(),
    ).date()
    default_cohort_starts = latest_quarter_starts(
        pd.Timestamp(max_date),
        pain_cohort_count,
        quarter_months,
    )
    pain_inputs, gamma_inputs = render_analysis_sidebar(
        min_date,
        max_date,
        default_pain_price_start,
        default_cohort_starts,
        settings["option_ticker_defaults"],
        market_inputs.index_name,
    )

    selected_range = st.slider(
        "表示期間",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="YYYY-MM-DD",
    )
    visible_data = filter_by_date(data, selected_range)
    if visible_data.empty:
        st.warning("選択期間にデータがありません。")
        return

    latest = data.dropna(subset=["Close"]).iloc[-1]
    previous_close = data["Close"].dropna().iloc[-2] if data["Close"].dropna().size >= 2 else None
    latest_close = latest.get("Close")
    latest_volume = latest.get("Volume")
    change = latest_close - previous_close if previous_close is not None else None
    change_pct = change / previous_close * 100 if previous_close not in (None, 0) else None
    quote_strip(
        latest_close,
        latest_volume,
        latest.get("Date"),
        change,
        change_pct,
        start_date,
        end_date,
    )

    left, right = st.columns([1.15, 0.85])
    with left:
        st.markdown('<div class="section-label">Intraday-style Chart: Close</div>', unsafe_allow_html=True)
        st.altair_chart(price_chart(visible_data), use_container_width=True)
    with right:
        st.markdown('<div class="section-label">Volume Bars</div>', unsafe_allow_html=True)
        st.altair_chart(volume_chart(visible_data), use_container_width=True)

    cohort_starts = (
        default_cohort_starts
        if pain_inputs.start_mode == "Quarter starts"
        else parse_date_list(pain_inputs.custom_start_dates)
    )
    pain_window, pain_data = calculate_pain_points(
        data,
        pd.Timestamp(pain_inputs.price_start),
        pd.Timestamp(pain_inputs.price_end),
        cohort_starts,
        tuple(settings["trend_lookbacks"]),
        settings["trend_vol_window"],
        settings["trend_signal_scale"],
    )
    if not pain_window.empty and not pain_data.empty:
        st.markdown('<div class="section-label">Accumulation Pain Points: Close Price</div>', unsafe_allow_html=True)
        st.altair_chart(pain_point_chart(pain_window, pain_data), use_container_width=True)
        st.markdown(
            """
            <div class="pain-note">
                Pain point = weighted average entry level using positive additions in the estimated trend-followers net position.
                The lower panel is a price-derived trend-followers position proxy from multi-horizon momentum.
                Positive distance means current Close is above that cohort's average entry level.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("Pain point chartに表示できるデータがありません。株価期間または開始日を確認してください。")

    if gamma_inputs.show_gamma:
        option_data, option_spot = load_option_chain(
            gamma_inputs.option_ticker.strip(),
            gamma_inputs.max_expiries,
            option_chain_client,
        )
        if option_data.empty or pd.isna(option_spot):
            st.warning(
                "Gamma exposureを計算できませんでした。Yahoo Financeからoption chainを取得できませんでした。"
                "Option ticker、ネットワーク接続、Yahoo Financeのoption chain availabilityを確認してください。"
            )
        else:
            gamma_profile = build_gamma_profile(
                option_data,
                option_spot,
                gamma_inputs.range_pct,
                gamma_inputs.steps,
                settings["contract_size"],
                settings["risk_free_rate"],
            )
            if gamma_profile.empty:
                st.warning("Gamma exposureの表示データがありません。")
            else:
                st.markdown(
                    '<div class="section-label">Current Gamma Exposure Across Spot Levels</div>',
                    unsafe_allow_html=True,
                )
                st.altair_chart(gamma_profile_chart(gamma_profile, option_spot), use_container_width=True)
                st.markdown(
                    f"""
                    <div class="pain-note">
                        Option ticker: {gamma_inputs.option_ticker.strip()} / Spot: {format_number(option_spot)} /
                        Contracts: {len(option_data):,}. Calls are signed positive and puts negative.
                        Gamma is estimated with Black-Scholes and displayed as $bn gamma per 1% spot move.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with st.expander("取得データ"):
        table_data = visible_data.sort_values("Date", ascending=False).reset_index(drop=True)
        numeric_columns = table_data.select_dtypes(include="number").columns.to_list()
        default_column_index = numeric_columns.index("High") if "High" in numeric_columns else 0
        aggregate_column = st.selectbox(
            "集計列",
            options=numeric_columns,
            index=default_column_index,
            help="左端のチェックボックスで選択した行について、この列の値だけを集計します。",
        )
        table_event = st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
        )
        selected_rows = table_event.selection.rows
        selected_values = selected_column_values(table_data, selected_rows, aggregate_column)
        render_selection_summary(selected_values, aggregate_column)
