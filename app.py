from __future__ import annotations

import math

import altair as alt
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


DEFAULT_TICKER = "^N225"
INDEX_OPTIONS = {
    "Nikkei 225": "^N225",
    "S&P 500": "^GSPC",
    "NASDAQ Composite": "^IXIC",
    "NASDAQ 100": "^NDX",
    "Dow Jones": "^DJI",
    "TOPIX": "^TOPX",
    "FTSE 100": "^FTSE",
    "DAX": "^GDAXI",
    "Hang Seng": "^HSI",
}
START_DATE = "2020-01-01"
END_DATE = "2026-05-01"
PAIN_WINDOW_YEARS = 2
QUARTER_MONTHS = 3
PAIN_COHORT_COUNT = 4
TREND_LOOKBACKS = (20, 60, 120, 250)
TREND_VOL_WINDOW = 60
TREND_SIGNAL_SCALE = 1.5
OPTION_TICKER_DEFAULTS = {
    "Nikkei 225": "EWJ",
    "S&P 500": "SPY",
    "NASDAQ Composite": "QQQ",
    "NASDAQ 100": "QQQ",
    "Dow Jones": "DIA",
    "TOPIX": "EWJ",
    "FTSE 100": "EWU",
    "DAX": "EWG",
    "Hang Seng": "EWH",
}
CONTRACT_SIZE = 100
RISK_FREE_RATE = 0.04


@st.cache_data(show_spinner="Market data loading...")
def load_market_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    data = yf.download(
        ticker,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()
    data["Date"] = pd.to_datetime(data["Date"])
    return data[["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]]


@st.cache_data(show_spinner="Option chain loading...", ttl=60 * 30)
def load_option_chain(option_ticker: str, max_expiries: int) -> tuple[pd.DataFrame, float]:
    try:
        data, spot = load_option_chain_yfinance(option_ticker, max_expiries)
    except Exception:
        data, spot = pd.DataFrame(), float("nan")

    if data.empty or pd.isna(spot):
        data, spot = load_option_chain_yahoo_api(option_ticker, max_expiries)

    if data.empty:
        return pd.DataFrame(), spot

    data = data[
        [
            "contractSymbol",
            "optionType",
            "expiry",
            "daysToExpiry",
            "strike",
            "openInterest",
            "impliedVolatility",
        ]
    ].copy()
    data["openInterest"] = pd.to_numeric(data["openInterest"], errors="coerce").fillna(0)
    data["impliedVolatility"] = pd.to_numeric(data["impliedVolatility"], errors="coerce")
    data["strike"] = pd.to_numeric(data["strike"], errors="coerce")
    data = data.dropna(subset=["strike", "impliedVolatility"])
    data = data[(data["openInterest"] > 0) & (data["impliedVolatility"] > 0) & (data["daysToExpiry"] > 0)]
    return data, spot


def load_option_chain_yfinance(option_ticker: str, max_expiries: int) -> tuple[pd.DataFrame, float]:
    ticker = yf.Ticker(option_ticker)
    history = ticker.history(period="5d", auto_adjust=False)
    if history.empty:
        return pd.DataFrame(), float("nan")

    spot = float(history["Close"].dropna().iloc[-1])
    expiries = list(ticker.options[:max_expiries])
    frames = []
    now = pd.Timestamp.utcnow().tz_localize(None)

    for expiry in expiries:
        chain = ticker.option_chain(expiry)
        for option_type, frame in (("call", chain.calls), ("put", chain.puts)):
            if frame.empty:
                continue
            option_data = frame.copy()
            option_data["optionType"] = option_type
            option_data["expiry"] = pd.to_datetime(expiry)
            option_data["daysToExpiry"] = (option_data["expiry"] - now).dt.total_seconds() / 86400
            frames.append(option_data)

    if not frames:
        return pd.DataFrame(), spot

    return pd.concat(frames, ignore_index=True), spot


def load_option_chain_yahoo_api(option_ticker: str, max_expiries: int) -> tuple[pd.DataFrame, float]:
    base_url = f"https://query2.finance.yahoo.com/v7/finance/options/{option_ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers, timeout=15)
    response.raise_for_status()
    root = response.json().get("optionChain", {}).get("result", [])
    if not root:
        return pd.DataFrame(), float("nan")

    first_result = root[0]
    quote = first_result.get("quote", {})
    spot = quote.get("regularMarketPrice") or quote.get("postMarketPrice") or float("nan")
    expiries = first_result.get("expirationDates", [])[:max_expiries]
    frames = []

    for expiry_ts in expiries:
        chain_response = requests.get(f"{base_url}?date={expiry_ts}", headers=headers, timeout=15)
        chain_response.raise_for_status()
        chain_root = chain_response.json().get("optionChain", {}).get("result", [])
        if not chain_root:
            continue
        options = chain_root[0].get("options", [])
        if not options:
            continue
        option_set = options[0]
        expiry_date = pd.to_datetime(expiry_ts, unit="s")
        for option_type, key in (("call", "calls"), ("put", "puts")):
            frame = pd.DataFrame(option_set.get(key, []))
            if frame.empty:
                continue
            frame["optionType"] = option_type
            frame["expiry"] = expiry_date
            frame["daysToExpiry"] = (expiry_date - pd.Timestamp.utcnow().tz_localize(None)).total_seconds() / 86400
            frames.append(frame)

    if not frames:
        return pd.DataFrame(), float(spot)

    return pd.concat(frames, ignore_index=True), float(spot)


def format_number(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:,.{digits}f}"


def norm_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi)


def black_scholes_gamma(spot: float, strike: float, volatility: float, time_to_expiry: float) -> float:
    if spot <= 0 or strike <= 0 or volatility <= 0 or time_to_expiry <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (RISK_FREE_RATE + 0.5 * volatility * volatility) * time_to_expiry) / (
        volatility * math.sqrt(time_to_expiry)
    )
    return norm_pdf(d1) / (spot * volatility * math.sqrt(time_to_expiry))


def build_gamma_profile(
    option_data: pd.DataFrame,
    spot: float,
    range_pct: float,
    steps: int,
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
            )
            sign = 1 if row.optionType == "call" else -1
            total_gamma += sign * gamma * float(row.openInterest) * CONTRACT_SIZE * level * level * 0.01
        rows.append({"SpotLevel": level, "GammaExposureBn": total_gamma / 1_000_000_000})

    return pd.DataFrame(rows)


def filter_by_date(data: pd.DataFrame, date_range: tuple[pd.Timestamp, pd.Timestamp]) -> pd.DataFrame:
    start, end = date_range
    return data[(data["Date"] >= pd.Timestamp(start)) & (data["Date"] <= pd.Timestamp(end))]


def clamp_date(value: pd.Timestamp, min_value: pd.Timestamp, max_value: pd.Timestamp) -> pd.Timestamp:
    return min(max(value, min_value), max_value)


def nearest_trading_date(data: pd.DataFrame, target: pd.Timestamp) -> pd.Timestamp | None:
    candidates = data[data["Date"] >= target]
    if candidates.empty:
        return None
    return candidates.iloc[0]["Date"]


def quarter_start(value: pd.Timestamp) -> pd.Timestamp:
    quarter_month = ((value.month - 1) // QUARTER_MONTHS) * QUARTER_MONTHS + 1
    return pd.Timestamp(year=value.year, month=quarter_month, day=1)


def latest_quarter_starts(end_date: pd.Timestamp, count: int) -> list[pd.Timestamp]:
    current = quarter_start(end_date)
    starts = []
    for _ in range(count):
        starts.append(current)
        current = current - pd.DateOffset(months=QUARTER_MONTHS)
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


def add_trend_position(data: pd.DataFrame) -> pd.DataFrame:
    result = data.sort_values("Date").copy()
    close = result["Close"].astype(float)
    returns = close.pct_change()
    vol = returns.rolling(TREND_VOL_WINDOW, min_periods=20).std()

    signals = []
    for lookback in TREND_LOOKBACKS:
        momentum = close.pct_change(lookback)
        zscore = momentum / (vol * lookback**0.5)
        signals.append((zscore / TREND_SIGNAL_SCALE).clip(-1, 1))

    signal_frame = pd.concat(signals, axis=1)
    result["TrendPosition"] = signal_frame.mean(axis=1).clip(-1, 1).fillna(0)
    return result


def weighted_pain_point(cohort: pd.DataFrame) -> pd.DataFrame:
    position = cohort["TrendPosition"].clip(lower=0).fillna(0)
    additions = position.diff().clip(lower=0).fillna(position)

    # If the model was already long and does not add, keep a minimal initial entry
    # so every cohort has a readable reference level.
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


def build_pain_points(
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

    cohort_dates = []
    for cohort_start in cohort_starts:
        if cohort_start > price_end:
            continue
        trading_date = nearest_trading_date(window, max(cohort_start, price_start))
        if trading_date is not None and trading_date not in cohort_dates:
            cohort_dates.append(trading_date)

    pain_frames = []
    for cohort_date in cohort_dates:
        cohort = window[window["Date"] >= cohort_date][["Date", "Close", "TrendPosition"]].copy()
        if cohort.empty:
            continue
        cohort = weighted_pain_point(cohort)
        cohort["Cohort"] = f"from {cohort_date.strftime('%b %Y')}"
        cohort["CohortDate"] = cohort_date
        pain_frames.append(cohort[["Date", "PainPoint", "PositionScore", "PositionAdd", "Cohort", "CohortDate"]])

    if not pain_frames:
        return window, pd.DataFrame()

    pain_data = pd.concat(pain_frames, ignore_index=True)
    latest_close = window.dropna(subset=["Close"]).iloc[-1]["Close"]
    latest_date = window.dropna(subset=["Close"]).iloc[-1]["Date"]
    labels = pain_data[pain_data["Date"] == latest_date].copy()
    labels["Distance"] = latest_close - labels["PainPoint"]
    labels["DistancePct"] = labels["Distance"] / labels["PainPoint"] * 100
    labels["Label"] = labels.apply(
        lambda row: f"{row['Cohort']}  {row['PainPoint']:,.0f}  {row['DistancePct']:+.1f}%",
        axis=1,
    )
    return window, pain_data.merge(labels[["Cohort", "Distance", "DistancePct", "Label"]], on="Cohort", how="left")


def selected_column_values(data: pd.DataFrame, selected_rows: list[int], selected_column: str) -> pd.Series:
    if not selected_rows or selected_column not in data.columns:
        return pd.Series(dtype="float64")

    values = pd.to_numeric(data.iloc[selected_rows][selected_column], errors="coerce").dropna()
    if values.empty:
        return pd.Series(dtype="float64")
    return values


def render_selection_summary(values: pd.Series, selected_column: str) -> None:
    if values.empty:
        st.markdown(
            """
            <div class="selection-summary">
                <span class="summary-empty">集計列を選び、左端のチェックボックスで行を選択すると、その列の選択セルだけを集計します。</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="selection-summary">
            <div class="summary-title">Selected Cells: {selected_column}</div>
            <div class="summary-grid">
                <div><span>Count</span><strong>{int(values.count()):,}</strong></div>
                <div><span>Sum</span><strong>{format_number(values.sum())}</strong></div>
                <div><span>Average</span><strong>{format_number(values.mean())}</strong></div>
                <div><span>Min</span><strong>{format_number(values.min())}</strong></div>
                <div><span>Max</span><strong>{format_number(values.max())}</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
            --cyan: #67e8f9;
            --muted: #a3aab8;
        }
        .stApp {
            background: var(--terminal-bg);
            color: #e6edf3;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stSidebar"] {
            background: #0b0d10;
            border-right: 1px solid var(--panel-border);
        }
        [data-testid="stSidebar"] * {
            color: #e6edf3;
        }
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
        h1, h2, h3, label, .stMarkdown, .stCaption {
            color: #e6edf3;
        }
        div[data-testid="stMetric"] {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 4px;
            padding: 10px 12px;
        }
        div[data-testid="stMetric"] label {
            color: var(--muted);
        }
        div[data-testid="stMetricValue"] {
            color: var(--amber);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        div[data-testid="stMetricDelta"] {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .stDataFrame {
            border: 1px solid var(--panel-border);
        }
        .pain-note {
            color: #cbd5e1;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            border: 1px solid var(--panel-border);
            background: #0b0d10;
            padding: 8px 10px;
            margin-top: 6px;
        }
        .selection-summary {
            margin-top: 8px;
            border: 1px solid var(--panel-border);
            background: #0b0d10;
            padding: 8px 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
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
        .summary-empty {
            color: #cbd5e1;
            font-size: 12px;
        }
        @media (max-width: 900px) {
            .market-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .quote-value {
                font-size: 20px;
            }
            .summary-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
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
                <div class="quote-value">{START_DATE}</div>
                <div class="quote-sub">to {END_DATE}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def price_chart(data: pd.DataFrame) -> alt.Chart:
    base = alt.Chart(data).encode(
        x=alt.X(
            "Date:T",
            title=None,
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
        ),
        tooltip=[
            alt.Tooltip("Date:T", title="日付", format="%Y-%m-%d"),
            alt.Tooltip("Open:Q", title="始値", format=",.2f"),
            alt.Tooltip("High:Q", title="高値", format=",.2f"),
            alt.Tooltip("Low:Q", title="安値", format=",.2f"),
            alt.Tooltip("Close:Q", title="終値", format=",.2f"),
        ],
    )
    area = base.mark_area(color="#0f4c81", opacity=0.35).encode(
        y=alt.Y("Close:Q", title=None),
    )
    line = base.mark_line(color="#67e8f9", strokeWidth=1.5).encode(
        y=alt.Y(
            "Close:Q",
            title=None,
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
        ),
    )
    points = base.mark_circle(size=28, color="#f6b500", opacity=0).encode(
        y="Close:Q",
    )
    return (
        (area + line + points)
        .properties(height=360)
        .configure_view(stroke="#31363f")
        .configure(background="#111419")
    ).interactive()


def volume_chart(data: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(data)
        .mark_bar(color="#f6b500", opacity=0.78)
        .encode(
            x=alt.X(
                "Date:T",
                title=None,
                axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
            ),
            y=alt.Y(
                "Volume:Q",
                title=None,
                axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="日付", format="%Y-%m-%d"),
                alt.Tooltip("Volume:Q", title="出来高", format=","),
                alt.Tooltip("Close:Q", title="終値", format=",.2f"),
            ],
        )
        .properties(height=360)
        .configure_view(stroke="#31363f")
        .configure(background="#111419")
    )


def gamma_profile_chart(profile: pd.DataFrame, spot: float) -> alt.Chart:
    base = alt.Chart(profile).encode(
        x=alt.X(
            "SpotLevel:Q",
            title="Spot level",
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041", format=",.0f"),
        ),
        y=alt.Y(
            "GammaExposureBn:Q",
            title="Gamma / 1% ($bn)",
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
        ),
        tooltip=[
            alt.Tooltip("SpotLevel:Q", title="Spot", format=",.2f"),
            alt.Tooltip("GammaExposureBn:Q", title="Gamma / 1% ($bn)", format=",.3f"),
        ],
    )
    area = base.mark_area(color="#0b3d91", opacity=0.95).encode(
        y="GammaExposureBn:Q",
        y2=alt.datum(0),
    )
    zero_rule = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#cbd5e1", opacity=0.65)
        .encode(y="y:Q")
    )
    spot_rule = (
        alt.Chart(pd.DataFrame({"SpotLevel": [spot]}))
        .mark_rule(color="#ff4d4f", strokeWidth=2)
        .encode(
            x="SpotLevel:Q",
            tooltip=[alt.Tooltip("SpotLevel:Q", title="Current spot", format=",.2f")],
        )
    )
    return (
        (area + zero_rule + spot_rule)
        .properties(height=360)
        .configure_view(stroke="#31363f")
        .configure(background="#111419")
    ).interactive()


def pain_point_chart(price_data: pd.DataFrame, pain_data: pd.DataFrame) -> alt.Chart:
    price_base = alt.Chart(price_data).encode(
        x=alt.X(
            "Date:T",
            title=None,
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
        )
    )
    close_line = price_base.mark_line(color="#e6edf3", strokeWidth=2.0).encode(
        y=alt.Y(
            "Close:Q",
            title=None,
            scale=alt.Scale(zero=False),
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
        ),
        tooltip=[
            alt.Tooltip("Date:T", title="日付", format="%Y-%m-%d"),
            alt.Tooltip("Close:Q", title="Close", format=",.2f"),
        ],
    )
    close_points = price_base.mark_circle(size=28, color="#e6edf3", opacity=0).encode(
        y="Close:Q",
        tooltip=[
            alt.Tooltip("Date:T", title="日付", format="%Y-%m-%d"),
            alt.Tooltip("Close:Q", title="Close", format=",.2f"),
        ],
    )
    latest = price_data.dropna(subset=["Close"]).tail(1)
    latest_rule = alt.Chart(latest).mark_rule(color="#f6b500", strokeDash=[4, 4]).encode(
        y="Close:Q",
        tooltip=[alt.Tooltip("Close:Q", title="Current Close", format=",.2f")],
    )
    pain_lines = (
        alt.Chart(pain_data)
        .mark_line(color="#ff4d4f", strokeDash=[6, 4], strokeWidth=1.6)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("PainPoint:Q", title=None),
            detail="Cohort:N",
            tooltip=[
                alt.Tooltip("Date:T", title="日付", format="%Y-%m-%d"),
                alt.Tooltip("Cohort:N", title="Cohort"),
                alt.Tooltip("PainPoint:Q", title="Pain point", format=",.2f"),
                alt.Tooltip("PositionScore:Q", title="Position score", format=".2f"),
                alt.Tooltip("PositionAdd:Q", title="Position add", format=".3f"),
                alt.Tooltip("Distance:Q", title="Close - Pain", format=",.2f"),
                alt.Tooltip("DistancePct:Q", title="Distance %", format="+.2f"),
            ],
        )
    )
    latest_pain = pain_data.sort_values("Date").groupby("Cohort", as_index=False).tail(1)
    pain_labels = (
        alt.Chart(latest_pain)
        .mark_text(
            align="left",
            baseline="middle",
            dx=8,
            color="#ffb4b4",
            font="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            fontSize=11,
        )
        .encode(
            x="Date:T",
            y="PainPoint:Q",
            text="Label:N",
            tooltip=[
                alt.Tooltip("Cohort:N", title="Cohort"),
                alt.Tooltip("PainPoint:Q", title="Pain point", format=",.2f"),
                alt.Tooltip("DistancePct:Q", title="Distance %", format="+.2f"),
            ],
        )
    )
    position_area = (
        alt.Chart(price_data)
        .mark_area(color="#5dade2", opacity=0.38, interpolate="step-after")
        .encode(
            x=alt.X(
                "Date:T",
                title=None,
                axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
            ),
            y=alt.Y(
                "TrendPosition:Q",
                title=None,
                scale=alt.Scale(domain=[-1, 1]),
                axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="日付", format="%Y-%m-%d"),
                alt.Tooltip("TrendPosition:Q", title="Trend-followers net position", format=".2f"),
            ],
        )
        .properties(height=120)
    )
    zero_rule = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="#cbd5e1", opacity=0.45)
        .encode(y="y:Q")
    )
    price_panel = close_line + close_points + latest_rule + pain_lines + pain_labels
    position_panel = position_area + zero_rule
    return (
        alt.vconcat(price_panel.properties(height=420), position_panel, spacing=4)
        .configure_view(stroke="#31363f")
        .configure(background="#111419")
    ).interactive()


def main() -> None:
    st.set_page_config(page_title="Index Analysis Terminal", layout="wide")
    inject_terminal_style()

    with st.sidebar:
        st.header("Market")
        index_name = st.selectbox("Index", options=list(INDEX_OPTIONS), index=0)
        ticker_source = st.radio("Ticker source", options=["Preset", "Custom"], horizontal=True)
        custom_ticker = st.text_input("Custom ticker", value=INDEX_OPTIONS[index_name])
        ticker = INDEX_OPTIONS[index_name] if ticker_source == "Preset" else custom_ticker.strip()
        st.caption(f"Data range: {START_DATE} - {END_DATE}")
        refresh = st.button("Reload data")

    if refresh:
        load_market_data.clear()

    if not ticker:
        st.error("ティッカーを入力してください。")
        return

    display_name = index_name if ticker_source == "Preset" else "Custom"
    terminal_header(display_name, ticker, START_DATE, END_DATE)

    data = load_market_data(ticker, START_DATE, END_DATE)

    if data.empty:
        st.error("データを取得できませんでした。ティッカーまたはネットワーク接続を確認してください。")
        return

    min_date = data["Date"].min().date()
    max_date = data["Date"].max().date()
    default_pain_price_start = clamp_date(
        data["Date"].max() - pd.DateOffset(years=PAIN_WINDOW_YEARS),
        data["Date"].min(),
        data["Date"].max(),
    ).date()
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
        default_cohort_starts = latest_quarter_starts(pd.Timestamp(pain_price_end), PAIN_COHORT_COUNT)
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
        default_option_ticker = OPTION_TICKER_DEFAULTS.get(index_name, "SPY")
        option_ticker = st.text_input(
            "Option ticker",
            value=default_option_ticker,
            help="Yahoo Financeでoption chainを取得できるティッカーを指定します。SPX指数そのものが取れない場合はSPYなどのETFを使います。",
        )
        max_expiries = st.slider("Expiries", min_value=1, max_value=12, value=6)
        gamma_range_pct = st.slider("Spot range +/- %", min_value=5, max_value=30, value=15)
        gamma_steps = st.slider("Spot steps", min_value=25, max_value=121, value=61, step=2)
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
    quote_strip(latest_close, latest_volume, latest.get("Date"), change, change_pct)

    left, right = st.columns([1.15, 0.85])
    with left:
        st.markdown('<div class="section-label">Intraday-style Chart: Close</div>', unsafe_allow_html=True)
        st.altair_chart(price_chart(visible_data), use_container_width=True)

    with right:
        st.markdown('<div class="section-label">Volume Bars</div>', unsafe_allow_html=True)
        st.altair_chart(volume_chart(visible_data), use_container_width=True)

    if pain_start_mode == "Quarter starts":
        cohort_starts = default_cohort_starts
    else:
        cohort_starts = parse_date_list(custom_cohort_text)

    pain_window, pain_data = build_pain_points(
        data,
        pd.Timestamp(pain_price_start),
        pd.Timestamp(pain_price_end),
        cohort_starts,
    )
    if not pain_window.empty and not pain_data.empty:
        st.markdown(
            '<div class="section-label">Accumulation Pain Points: Close Price</div>',
            unsafe_allow_html=True,
        )
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

    if show_gamma:
        option_data, option_spot = load_option_chain(option_ticker.strip(), max_expiries)
        if option_data.empty or pd.isna(option_spot):
            st.warning(
                "Gamma exposureを計算できませんでした。yfinanceとYahoo option APIの両方でoption chainを取得できませんでした。"
                "Option ticker、ネットワーク接続、Yahoo Financeのoption chain availabilityを確認してください。"
            )
        else:
            gamma_profile = build_gamma_profile(option_data, option_spot, gamma_range_pct, gamma_steps)
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
                        Option ticker: {option_ticker.strip()} / Spot: {format_number(option_spot)} /
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


if __name__ == "__main__":
    main()
