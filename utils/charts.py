"""
charts.py - Intelligent, context-aware chart selection engine.

Decision logic picks the BEST chart type for each specific data shape:
- KPI single value        → Big metric indicator card
- Time series             → Line / area chart
- Trend + breakdown       → Multi-line chart
- Ranking (top N)         → Horizontal bar chart
- Part-of-whole           → Donut chart (≤8 cats) or treemap (>8)
- Distribution            → Histogram with KDE overlay
- Correlation (2 metrics) → Scatter with trendline
- Correlation matrix      → Heatmap
- Funnel / ordered stages → Funnel chart
- Geographic              → Choropleth (if country/state col detected)
- Multi-metric comparison → Grouped bar chart
- Cumulative / running    → Area chart
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objects import Figure
from plotly.subplots import make_subplots


# ── Dark theme palette ──────────────────────────────────────────────
THEME = "plotly_dark"
PRIMARY   = "#6346ff"
SECONDARY = "#00d2be"
ACCENT    = "#ff6b9d"
GOLD      = "#f7b731"
PALETTE   = [PRIMARY, SECONDARY, ACCENT, GOLD, "#a78bfa", "#34d399", "#fb923c", "#60a5fa"]

LAYOUT = dict(
    template=THEME,
    paper_bgcolor="rgba(13,13,20,0)",
    plot_bgcolor="rgba(13,13,20,0)",
    font=dict(family="DM Sans, sans-serif", color="#9896b0", size=12),
    title_font=dict(family="Syne, sans-serif", color="#e8e6f0", size=15),
    margin=dict(t=50, b=40, l=40, r=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=11)),
    colorway=PALETTE,
)

AXIS_STYLE = dict(
    gridcolor="rgba(255,255,255,0.05)",
    zerolinecolor="rgba(255,255,255,0.08)",
    tickfont=dict(size=11, color="#5e5c78"),
    title_font=dict(size=12, color="#7a7890"),
)


# ── Column type helpers ─────────────────────────────────────────────

def _numeric_cols(df):
    return df.select_dtypes(include="number").columns.tolist()

def _cat_cols(df):
    return df.select_dtypes(include="object").columns.tolist()

def _date_cols(df):
    found = []
    DATE_KEYWORDS = ["date", "month", "year", "week", "day", "period", "time", "quarter"]
    for col in df.columns:
        if any(kw in col.lower() for kw in DATE_KEYWORDS):
            found.append(col)
        elif df[col].dtype == object:
            try:
                sample = df[col].dropna().head(5)
                pd.to_datetime(sample)
                found.append(col)
            except Exception:
                pass
    return found

def _geo_cols(df):
    GEO_KEYWORDS = ["country", "nation", "state", "region", "city", "province", "territory"]
    return [c for c in df.columns if any(kw in c.lower() for kw in GEO_KEYWORDS)]

def _is_ranking(df, cat_col, num_col):
    """True if data looks like a top-N ranking (few rows, sorted by value)."""
    return len(df) <= 30 and df[num_col].is_monotonic_decreasing or len(df) <= 20

def _is_percentage(df, col):
    vals = df[col].dropna()
    return vals.between(0, 1).all() or vals.between(0, 100).all()

def _is_cumulative(title):
    keywords = ["cumul", "running", "total over", "growth", "ytd", "mtd"]
    return any(kw in title.lower() for kw in keywords)

def _is_distribution(title):
    keywords = ["distribut", "spread", "histogram", "range", "frequency", "how many"]
    return any(kw in title.lower() for kw in keywords)

def _is_correlation(title):
    keywords = ["vs", "versus", "correlat", "relationship", "scatter", "compare"]
    return any(kw in title.lower() for kw in keywords)

def _is_funnel(title):
    keywords = ["funnel", "stage", "step", "conversion", "pipeline", "drop"]
    return any(kw in title.lower() for kw in keywords)

def _is_part_of_whole(title):
    keywords = ["share", "breakdown", "proportion", "percent", "mix", "composition", "split", "by"]
    return any(kw in title.lower() for kw in keywords)

def _apply_layout(fig, title=""):
    fig.update_layout(**LAYOUT)
    if title:
        fig.update_layout(title_text=title)
    # Style axes
    if hasattr(fig, "layout") and hasattr(fig.layout, "xaxis"):
        fig.update_xaxes(**AXIS_STYLE)
        fig.update_yaxes(**AXIS_STYLE)
    return fig


# ── Main dispatcher ─────────────────────────────────────────────────

def auto_chart(df: pd.DataFrame, title: str = "") -> Figure | None:
    """
    Intelligently pick and render the best chart for this DataFrame.
    Uses column types, cardinality, row count, and title keywords.
    """
    if df is None or df.empty:
        return None

    df = df.copy()

    numeric = _numeric_cols(df)
    cats    = _cat_cols(df)
    dates   = _date_cols(df)
    geos    = _geo_cols(df)
    rows, ncols = df.shape

    # ── 1. Single KPI value ─────────────────────────────────────────
    if rows == 1 and len(numeric) >= 1:
        if len(numeric) == 1:
            return _kpi_single(df, numeric[0], title)
        else:
            return _kpi_multi(df, numeric[:4], title)

    # ── 2. Funnel chart ────────────────────────────────────────────
    if _is_funnel(title) and cats and numeric:
        return _funnel(df, cats[0], numeric[0], title)

    # ── 3. Geographic choropleth ───────────────────────────────────
    if geos and numeric:
        return _choropleth(df, geos[0], numeric[0], title)

    # ── 4. Correlation matrix (many numerics, no cats) ─────────────
    if len(numeric) >= 4 and not dates and not cats:
        return _heatmap_corr(df, numeric, title)

    # ── 5. Scatter (2 numerics, correlation intent) ─────────────────
    if len(numeric) >= 2 and (_is_correlation(title) or (not dates and not cats)):
        if rows > 5:
            return _scatter(df, numeric[0], numeric[1], cats[0] if cats else None, title)

    # ── 6. Time series ─────────────────────────────────────────────
    if dates and numeric:
        x = dates[0]
        try:
            df[x] = pd.to_datetime(df[x])
            df = df.sort_values(x)
        except Exception:
            pass

        # Multi-line: date + category + numeric
        if cats and len(df[cats[0]].unique()) <= 8 and not _is_cumulative(title):
            return _multiline(df, x, numeric[0], cats[0], title)

        # Cumulative / area
        if _is_cumulative(title):
            return _area(df, x, numeric[0], title)

        # Simple line
        return _line(df, x, numeric[0], title)

    # ── 7. Distribution ─────────────────────────────────────────────
    if _is_distribution(title) and numeric:
        return _histogram(df, numeric[0], title)

    # ── 8. Category + numeric ───────────────────────────────────────
    if cats and numeric:
        cat_col  = cats[0]
        num_col  = numeric[0]
        n_cats   = df[cat_col].nunique()

        # Part-of-whole → donut or treemap
        if _is_part_of_whole(title):
            if n_cats <= 8:
                return _donut(df, cat_col, num_col, title)
            else:
                return _treemap(df, cat_col, num_col, title)

        # Multi-metric grouped bar
        if len(numeric) >= 2:
            return _grouped_bar(df, cat_col, numeric[:3], title)

        # Ranking → horizontal bar
        if n_cats <= 25:
            return _hbar(df, cat_col, num_col, title)

        # Too many cats → treemap
        return _treemap(df, cat_col, num_col, title)

    # ── 9. Single numeric distribution fallback ──────────────────────
    if len(numeric) == 1 and rows > 5:
        return _histogram(df, numeric[0], title)

    # ── 10. Two+ numerics fallback ──────────────────────────────────
    if len(numeric) >= 2:
        return _scatter(df, numeric[0], numeric[1], None, title)

    return None


# ── Chart renderers ─────────────────────────────────────────────────

def _kpi_single(df, col, title):
    value = df[col].iloc[0]
    fig = go.Figure(go.Indicator(
        mode="number",
        value=float(value),
        title={"text": title or col, "font": {"size": 14, "color": "#9896b0"}},
        number={
            "font": {"size": 56, "color": "#f0eeff", "family": "Syne"},
            "valueformat": ",.2f" if isinstance(value, float) else ",d",
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(**LAYOUT, height=180)
    return fig


def _kpi_multi(df, cols, title):
    n = len(cols)
    fig = make_subplots(
        rows=1, cols=n,
        specs=[[{"type": "indicator"}] * n],
    )
    for i, col in enumerate(cols):
        value = df[col].iloc[0]
        fig.add_trace(go.Indicator(
            mode="number",
            value=float(value),
            title={"text": col, "font": {"size": 12, "color": "#9896b0"}},
            number={"font": {"size": 36, "color": PALETTE[i % len(PALETTE)], "family": "Syne"}},
        ), row=1, col=i + 1)
    fig.update_layout(**LAYOUT, height=180, title_text=title)
    return fig


def _line(df, x, y, title):
    fig = px.line(df, x=x, y=y, title=title or f"{y} over time",
                  markers=True, color_discrete_sequence=[PRIMARY])
    fig.update_traces(line_width=2.5, marker_size=5)
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _area(df, x, y, title):
    fig = px.area(df, x=x, y=y, title=title or f"Cumulative {y}",
                  color_discrete_sequence=[PRIMARY])
    fig.update_traces(
        fillcolor=f"rgba(99,70,255,0.15)",
        line_color=PRIMARY, line_width=2,
    )
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _multiline(df, x, y, color, title):
    fig = px.line(df, x=x, y=y, color=color,
                  title=title or f"{y} by {color} over time",
                  markers=True, color_discrete_sequence=PALETTE)
    fig.update_traces(line_width=2, marker_size=4)
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _hbar(df, cat, num, title):
    """Horizontal bar — best for rankings and comparisons."""
    df_s = df.nlargest(20, num) if len(df) > 20 else df.sort_values(num, ascending=False)
    df_s = df_s.sort_values(num, ascending=True)  # ascending for hbar readability

    fig = px.bar(
        df_s, y=cat, x=num, orientation="h",
        title=title or f"{num} by {cat}",
        color=num, color_continuous_scale=[[0, "rgba(99,70,255,0.3)"], [1, PRIMARY]],
    )
    fig.update_layout(**LAYOUT, coloraxis_showscale=False,
                      height=max(300, len(df_s) * 28 + 80))
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE, tickfont=dict(size=11, color="#c8c5e8"))
    fig.update_traces(marker_line_width=0)
    return fig


def _grouped_bar(df, cat, num_cols, title):
    fig = go.Figure()
    for i, col in enumerate(num_cols):
        fig.add_trace(go.Bar(
            name=col,
            x=df[cat],
            y=df[col],
            marker_color=PALETTE[i % len(PALETTE)],
            marker_line_width=0,
        ))
    fig.update_layout(**LAYOUT, barmode="group",
                      title_text=title or f"Comparison by {cat}")
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _donut(df, cat, num, title):
    """Donut chart — best for part-of-whole with ≤8 categories."""
    fig = px.pie(
        df, names=cat, values=num,
        title=title or f"{num} breakdown",
        color_discrete_sequence=PALETTE,
        hole=0.55,
    )
    fig.update_traces(
        textposition="outside",
        textfont_size=11,
        marker_line_color="rgba(0,0,0,0.3)",
        marker_line_width=1.5,
        pull=[0.03] * len(df),
    )
    fig.update_layout(**LAYOUT)
    return fig


def _treemap(df, cat, num, title):
    """Treemap — best for part-of-whole with many categories."""
    fig = px.treemap(
        df, path=[cat], values=num,
        title=title or f"{num} by {cat}",
        color=num,
        color_continuous_scale=[[0, "rgba(99,70,255,0.4)"], [0.5, "#6346ff"], [1, "#00d2be"]],
    )
    fig.update_traces(textfont_size=12)
    fig.update_layout(**LAYOUT)
    return fig


def _scatter(df, x, y, color, title):
    """Scatter with trendline — best for correlation analysis."""
    kwargs = dict(
        x=x, y=y, title=title or f"{y} vs {x}",
        color_discrete_sequence=[PRIMARY],
        trendline="ols",
        trendline_color_override=SECONDARY,
    )
    if color:
        kwargs["color"] = color
        kwargs["color_discrete_sequence"] = PALETTE

    try:
        fig = px.scatter(df, **kwargs)
    except Exception:
        kwargs.pop("trendline", None)
        kwargs.pop("trendline_color_override", None)
        fig = px.scatter(df, **kwargs)

    fig.update_traces(marker_size=7, marker_opacity=0.75,
                      selector=dict(mode="markers"))
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _histogram(df, col, title):
    """Histogram with KDE-style smooth overlay."""
    fig = px.histogram(
        df, x=col,
        title=title or f"Distribution of {col}",
        color_discrete_sequence=[PRIMARY],
        nbins=min(40, max(10, len(df) // 5)),
        marginal="box",
    )
    fig.update_traces(marker_line_width=0, opacity=0.8)
    fig.update_layout(**LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def _heatmap_corr(df, num_cols, title):
    """Correlation heatmap — best for multi-metric analysis."""
    corr = df[num_cols].corr().round(2)
    fig = px.imshow(
        corr,
        text_auto=True,
        title=title or "Correlation Matrix",
        color_continuous_scale=[[0, "#ff6b9d"], [0.5, "#0a0a0f"], [1, "#00d2be"]],
        zmin=-1, zmax=1,
        aspect="auto",
    )
    fig.update_traces(textfont_size=10)
    fig.update_layout(**LAYOUT)
    return fig


def _funnel(df, cat, num, title):
    """Funnel chart — best for conversion/pipeline stages."""
    df_s = df.sort_values(num, ascending=False)
    fig = go.Figure(go.Funnel(
        y=df_s[cat],
        x=df_s[num],
        textinfo="value+percent initial",
        marker_color=PALETTE[:len(df_s)],
        connector_line_color="rgba(255,255,255,0.1)",
    ))
    fig.update_layout(**LAYOUT, title_text=title or "Funnel")
    return fig


def _choropleth(df, geo_col, num_col, title):
    """World choropleth — best for country-level data."""
    # Detect if country or US state
    sample_vals = df[geo_col].dropna().head(10).tolist()
    is_us_state = any(len(str(v)) == 2 for v in sample_vals)

    try:
        if is_us_state:
            fig = px.choropleth(
                df, locations=geo_col,
                locationmode="USA-states",
                color=num_col,
                title=title or f"{num_col} by State",
                color_continuous_scale=[[0, "rgba(99,70,255,0.2)"], [1, PRIMARY]],
                scope="usa",
            )
        else:
            fig = px.choropleth(
                df, locations=geo_col,
                locationmode="country names",
                color=num_col,
                title=title or f"{num_col} by Country",
                color_continuous_scale=[[0, "rgba(99,70,255,0.2)"], [1, PRIMARY]],
            )
        fig.update_layout(**LAYOUT)
        return fig
    except Exception:
        # Fallback to hbar if geo fails
        return _hbar(df, geo_col, num_col, title)
