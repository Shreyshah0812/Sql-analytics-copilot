"""
charts.py - Automatic chart selection and rendering with Plotly.
Picks the best chart type based on column types in the result DataFrame.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objects import Figure


def detect_date_columns(df: pd.DataFrame) -> list[str]:
    """Try to detect date-like columns by name and content."""
    date_cols = []
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["date", "month", "year", "week", "day", "period"]):
            date_cols.append(col)
        elif df[col].dtype == object:
            # Try parsing a sample
            try:
                pd.to_datetime(df[col].dropna().head(5))
                date_cols.append(col)
            except Exception:
                pass
    return date_cols


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="number").columns.tolist()


def get_categorical_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="object").columns.tolist()


def auto_chart(df: pd.DataFrame, title: str = "") -> Figure | None:
    """
    Automatically select and render the best chart for the DataFrame.

    Rules:
    - 1 row (KPI): big metric card
    - Date col + numeric → line chart
    - Category + numeric → bar chart
    - 2 numerics → scatter
    - Single numeric col, many rows → histogram
    """
    if df.empty:
        return None

    numeric_cols = get_numeric_columns(df)
    cat_cols = get_categorical_columns(df)
    date_cols = detect_date_columns(df)

    rows, cols = df.shape

    # Single KPI value
    if rows == 1 and len(numeric_cols) == 1:
        return _kpi_card(df, numeric_cols[0], title)

    # Time series: date + 1+ numerics
    if date_cols and numeric_cols:
        x_col = date_cols[0]
        y_col = numeric_cols[0]
        color_col = cat_cols[0] if cat_cols else None
        try:
            df[x_col] = pd.to_datetime(df[x_col])
            df = df.sort_values(x_col)
        except Exception:
            pass
        return px.line(
            df, x=x_col, y=y_col,
            color=color_col,
            title=title or f"{y_col} over {x_col}",
            template="plotly_white",
        )

    # Category + numeric → bar chart
    if cat_cols and numeric_cols:
        x_col = cat_cols[0]
        y_col = numeric_cols[0]
        df_sorted = df.sort_values(y_col, ascending=False).head(20)
        return px.bar(
            df_sorted, x=x_col, y=y_col,
            title=title or f"{y_col} by {x_col}",
            template="plotly_white",
            color=y_col,
            color_continuous_scale="Blues",
        )

    # Two numerics → scatter
    if len(numeric_cols) >= 2:
        label_col = cat_cols[0] if cat_cols else None
        return px.scatter(
            df, x=numeric_cols[0], y=numeric_cols[1],
            hover_name=label_col,
            title=title or f"{numeric_cols[1]} vs {numeric_cols[0]}",
            template="plotly_white",
        )

    # Single numeric → histogram
    if len(numeric_cols) == 1 and rows > 1:
        return px.histogram(
            df, x=numeric_cols[0],
            title=title or f"Distribution of {numeric_cols[0]}",
            template="plotly_white",
        )

    return None


def _kpi_card(df: pd.DataFrame, col: str, title: str) -> Figure:
    """Render a big KPI metric card."""
    value = df[col].iloc[0]
    formatted = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"

    fig = go.Figure(go.Indicator(
        mode="number",
        value=float(value),
        title={"text": title or col, "font": {"size": 20}},
        number={"font": {"size": 60}},
    ))
    fig.update_layout(height=200, margin=dict(t=40, b=20, l=20, r=20))
    return fig
