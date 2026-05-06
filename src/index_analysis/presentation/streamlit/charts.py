from __future__ import annotations

import altair as alt
import pandas as pd


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
    area = base.mark_area(color="#0f4c81", opacity=0.35).encode(y=alt.Y("Close:Q", title=None))
    line = base.mark_line(color="#67e8f9", strokeWidth=1.5).encode(
        y=alt.Y(
            "Close:Q",
            title=None,
            axis=alt.Axis(labelColor="#cbd5e1", tickColor="#46505f", gridColor="#253041"),
        ),
    )
    points = base.mark_circle(size=28, color="#f6b500", opacity=0).encode(y="Close:Q")
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
    area = base.mark_area(color="#0b3d91", opacity=0.95).encode(y="GammaExposureBn:Q", y2=alt.datum(0))
    zero_rule = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#cbd5e1", opacity=0.65).encode(y="y:Q")
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
    zero_rule = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#cbd5e1", opacity=0.45).encode(y="y:Q")
    price_panel = close_line + close_points + latest_rule + pain_lines + pain_labels
    position_panel = position_area + zero_rule
    return (
        alt.vconcat(price_panel.properties(height=420), position_panel, spacing=4)
        .configure_view(stroke="#31363f")
        .configure(background="#111419")
    ).interactive()
