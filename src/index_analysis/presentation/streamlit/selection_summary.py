from __future__ import annotations

import pandas as pd
import streamlit as st


def format_number(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:,.{digits}f}"


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
