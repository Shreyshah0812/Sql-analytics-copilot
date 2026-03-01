"""
app.py - SQL + Analytics Copilot (Redesigned)
Clean onboarding flow: Upload → Overview → Deep Insights
"""

import os
import tempfile
import yaml
import pandas as pd
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

from utils.db import get_sqlite_schema, run_sqlite_query, get_csv_schema, run_csv_query, seed_sample_db
from utils.llm import generate_sql, fix_sql, explain_results
from utils.guardrails import validate_sql, GuardrailError
from utils.charts import auto_chart
from utils.validators import run_validations

load_dotenv()

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DataMind — Analytics Copilot",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# Global styles
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [data-testid="stAppViewContainer"] {
    background: #0a0a0f;
    color: #e8e6f0;
    font-family: 'DM Sans', sans-serif;
}

[data-testid="stAppViewContainer"] {
    background: #0a0a0f;
}

[data-testid="stHeader"] { display: none; }
[data-testid="stSidebar"] { display: none; }
.stDeployButton { display: none; }
#MainMenu { display: none; }
footer { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #2d2b3d; border-radius: 2px; }

/* ── Upload Screen ── */
.upload-screen {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    position: relative;
    overflow: hidden;
}

.upload-screen::before {
    content: '';
    position: fixed;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 60% 40%, rgba(99, 70, 255, 0.08) 0%, transparent 60%),
                radial-gradient(ellipse at 20% 80%, rgba(0, 210, 190, 0.05) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
}

.brand-logo {
    font-family: 'Syne', sans-serif;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #6346ff;
    margin-bottom: 60px;
    position: relative;
    z-index: 1;
}

.brand-logo span {
    color: #00d2be;
}

.hero-title {
    font-family: 'Syne', sans-serif;
    font-size: clamp(36px, 6vw, 72px);
    font-weight: 800;
    line-height: 1.05;
    text-align: center;
    color: #f0eeff;
    margin-bottom: 20px;
    position: relative;
    z-index: 1;
}

.hero-title .accent {
    background: linear-gradient(135deg, #6346ff, #00d2be);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.hero-sub {
    font-size: 17px;
    color: #7a7890;
    text-align: center;
    margin-bottom: 56px;
    max-width: 440px;
    line-height: 1.6;
    font-weight: 300;
    position: relative;
    z-index: 1;
}

/* ── Upload Box ── */
.upload-wrapper {
    width: 100%;
    max-width: 520px;
    position: relative;
    z-index: 1;
}

[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1.5px dashed rgba(99, 70, 255, 0.4) !important;
    border-radius: 16px !important;
    padding: 40px !important;
    transition: all 0.3s ease !important;
}

[data-testid="stFileUploader"]:hover {
    border-color: rgba(99, 70, 255, 0.8) !important;
    background: rgba(99, 70, 255, 0.04) !important;
}

[data-testid="stFileUploader"] label {
    color: #9896b0 !important;
    font-family: 'DM Sans', sans-serif !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] {
    color: #9896b0 !important;
}

/* Sample DB button area */
.divider-text {
    text-align: center;
    color: #3d3b52;
    font-size: 13px;
    margin: 20px 0;
    position: relative;
    z-index: 1;
}

/* ── Overview Screen ── */
.overview-screen {
    max-width: 1100px;
    margin: 0 auto;
    padding: 48px 32px;
}

.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 48px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

.nav-brand {
    font-family: 'Syne', sans-serif;
    font-size: 18px;
    font-weight: 700;
    color: #6346ff;
    letter-spacing: 0.1em;
}

.file-badge {
    background: rgba(99, 70, 255, 0.12);
    border: 1px solid rgba(99, 70, 255, 0.3);
    color: #a89fff;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-family: 'DM Sans', sans-serif;
}

.overview-title {
    font-family: 'Syne', sans-serif;
    font-size: 32px;
    font-weight: 800;
    color: #f0eeff;
    margin-bottom: 8px;
}

.overview-sub {
    color: #5e5c78;
    font-size: 15px;
    margin-bottom: 40px;
}

/* Stat cards */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 40px;
}

.stat-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 24px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    border-radius: 14px 14px 0 0;
}

.stat-card.purple::before { background: linear-gradient(90deg, #6346ff, #9b7dff); }
.stat-card.teal::before   { background: linear-gradient(90deg, #00d2be, #00a8e8); }
.stat-card.pink::before   { background: linear-gradient(90deg, #ff6b9d, #ff9b6b); }
.stat-card.gold::before   { background: linear-gradient(90deg, #f7b731, #fd9644); }

.stat-label {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #5e5c78;
    margin-bottom: 10px;
}

.stat-value {
    font-family: 'Syne', sans-serif;
    font-size: 34px;
    font-weight: 800;
    color: #f0eeff;
    line-height: 1;
}

.stat-detail {
    font-size: 12px;
    color: #4a4860;
    margin-top: 6px;
}

/* Column preview table */
.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #c8c5e8;
    margin-bottom: 16px;
    letter-spacing: 0.02em;
}

/* Deep Insights button */
.insights-btn-wrap {
    margin-top: 40px;
    display: flex;
    justify-content: center;
}

/* ── Chat Screen ── */
.chat-screen {
    max-width: 960px;
    margin: 0 auto;
    padding: 32px 24px 120px;
}

.chat-nav {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 40px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

.back-btn-style {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    color: #7a7890;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
}

.chat-title {
    font-family: 'Syne', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #f0eeff;
}

.chat-file-tag {
    margin-left: auto;
    background: rgba(0, 210, 190, 0.1);
    border: 1px solid rgba(0, 210, 190, 0.25);
    color: #00d2be;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
}

/* Chat messages */
.user-msg {
    background: rgba(99, 70, 255, 0.12);
    border: 1px solid rgba(99, 70, 255, 0.2);
    border-radius: 16px 16px 4px 16px;
    padding: 14px 18px;
    margin-bottom: 20px;
    color: #d4d0f5;
    font-size: 15px;
    max-width: 75%;
    margin-left: auto;
}

.assistant-block {
    margin-bottom: 32px;
}

/* SQL block */
.sql-block {
    background: #0d0d14;
    border: 1px solid rgba(99, 70, 255, 0.2);
    border-left: 3px solid #6346ff;
    border-radius: 0 10px 10px 0;
    padding: 16px 20px;
    margin-bottom: 16px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    color: #a89fff;
    overflow-x: auto;
}

/* Streamlit overrides for dark theme */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
    gap: 0 !important;
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #5e5c78 !important;
    border: none !important;
    padding: 10px 20px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 13px !important;
}

.stTabs [aria-selected="true"] {
    color: #a89fff !important;
    border-bottom: 2px solid #6346ff !important;
}

.stTabs [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding-top: 20px !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* Buttons */
.stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6346ff, #8066ff) !important;
    border: none !important;
    color: white !important;
    padding: 12px 28px !important;
    font-size: 15px !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #7356ff, #9076ff) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 24px rgba(99, 70, 255, 0.3) !important;
}

.stButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #9896b0 !important;
}

/* Chat input */
[data-testid="stChatInput"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(99, 70, 255, 0.3) !important;
    border-radius: 14px !important;
}

[data-testid="stChatInput"] textarea {
    color: #e8e6f0 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* Warning / info */
.stAlert {
    background: rgba(247, 183, 49, 0.06) !important;
    border: 1px solid rgba(247, 183, 49, 0.2) !important;
    border-radius: 10px !important;
    color: #f7b731 !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    color: #9896b0 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* Spinner */
.stSpinner > div { border-top-color: #6346ff !important; }

/* Download button */
.stDownloadButton > button {
    background: rgba(0, 210, 190, 0.08) !important;
    border: 1px solid rgba(0, 210, 190, 0.25) !important;
    color: #00d2be !important;
    border-radius: 8px !important;
    font-size: 13px !important;
}

/* Radio */
[data-testid="stRadio"] label { color: #9896b0 !important; }

/* Suggestion chips */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 28px;
}

</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────
def init_state():
    defaults = {
        "screen": "upload",       # upload | overview | chat
        "db_mode": None,
        "csv_path": None,
        "schema": "",
        "df_preview": None,
        "filename": "",
        "chat_history": [],
        "llm_history": [],
        "last_sql": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
@st.cache_data
def load_kpis() -> str:
    kpi_path = Path("metrics/kpis.yaml")
    if not kpi_path.exists():
        return ""
    with open(kpi_path) as f:
        kpis = yaml.safe_load(f)
    lines = []
    for name, info in kpis.items():
        if isinstance(info, dict):
            lines.append(f"- {name}: {info.get('definition', '')}")
        else:
            lines.append(f"- {name}: {info}")
    return "\n".join(lines)


def get_data_stats(df: pd.DataFrame):
    rows, cols = df.shape
    nulls = int(df.isnull().sum().sum())
    num_cols = len(df.select_dtypes(include="number").columns)
    cat_cols = len(df.select_dtypes(include="object").columns)
    return rows, cols, nulls, num_cols, cat_cols


def run_query(sql: str):
    if st.session_state.db_mode == "sample":
        return run_sqlite_query("db/sample.db", sql)
    else:
        return run_csv_query(st.session_state.csv_path, sql)


# ─────────────────────────────────────────────
# SCREEN 1: UPLOAD
# ─────────────────────────────────────────────
if st.session_state.screen == "upload":

    st.markdown("""
    <div class="upload-screen">
        <div class="brand-logo">Data<span>Mind</span> ✦</div>
        <div class="hero-title">
            Ask your data<br>anything. <span class="accent">Instantly.</span>
        </div>
        <div class="hero-sub">
            Upload a CSV and get SQL-powered insights, charts,<br>and analysis — in plain English.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        uploaded = st.file_uploader(
            "Drop your CSV file here",
            type=["csv"],
            label_visibility="collapsed",
        )

        if uploaded:
            with st.spinner("Reading your data..."):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
                tmp.write(uploaded.read())
                tmp.flush()
                df = pd.read_csv(tmp.name)
                schema = get_csv_schema(tmp.name)

                st.session_state.csv_path = tmp.name
                st.session_state.db_mode = "csv"
                st.session_state.schema = schema
                st.session_state.df_preview = df
                st.session_state.filename = uploaded.name
                st.session_state.screen = "overview"
                st.rerun()

        st.markdown('<div class="divider-text">— or try our sample dataset —</div>', unsafe_allow_html=True)

        if st.button("Use Sample Database (Music Store)", use_container_width=True, type="secondary"):
            seed_sample_db("db/sample.db")
            schema = get_sqlite_schema("db/sample.db")
            df = run_sqlite_query("db/sample.db", "SELECT * FROM invoices LIMIT 500")
            st.session_state.db_mode = "sample"
            st.session_state.schema = schema
            st.session_state.df_preview = df
            st.session_state.filename = "Music Store (Sample)"
            st.session_state.screen = "overview"
            st.rerun()


# ─────────────────────────────────────────────
# SCREEN 2: DATA OVERVIEW
# ─────────────────────────────────────────────
elif st.session_state.screen == "overview":
    df = st.session_state.df_preview
    rows, cols, nulls, num_cols, cat_cols = get_data_stats(df)

    st.markdown(f"""
    <div class="overview-screen">
        <div class="nav-bar">
            <div class="nav-brand">DataMind ✦</div>
            <div class="file-badge">📄 {st.session_state.filename}</div>
        </div>
        <div class="overview-title">Your Data is Ready</div>
        <div class="overview-sub">Here's a quick overview of what was loaded.</div>
        <div class="stats-grid">
            <div class="stat-card purple">
                <div class="stat-label">Total Rows</div>
                <div class="stat-value">{rows:,}</div>
                <div class="stat-detail">records loaded</div>
            </div>
            <div class="stat-card teal">
                <div class="stat-label">Columns</div>
                <div class="stat-value">{cols}</div>
                <div class="stat-detail">{num_cols} numeric · {cat_cols} text</div>
            </div>
            <div class="stat-card pink">
                <div class="stat-label">Missing Values</div>
                <div class="stat-value">{nulls:,}</div>
                <div class="stat-detail">{'clean dataset ✓' if nulls == 0 else 'across all columns'}</div>
            </div>
            <div class="stat-card gold">
                <div class="stat-label">Memory</div>
                <div class="stat-value">{df.memory_usage(deep=True).sum() / 1024:.0f}K</div>
                <div class="stat-detail">in memory</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Column overview
    st.markdown('<div class="section-title">📋 Column Overview</div>', unsafe_allow_html=True)
    col_info = pd.DataFrame({
        "Column": df.columns,
        "Type": df.dtypes.astype(str).values,
        "Non-Null": df.count().values,
        "Null %": (df.isnull().mean() * 100).round(1).astype(str) + "%",
        "Sample Value": [str(df[c].dropna().iloc[0]) if df[c].dropna().shape[0] > 0 else "—" for c in df.columns],
    })
    st.dataframe(col_info, use_container_width=True, hide_index=True, height=280)

    # Data preview
    with st.expander("👁️ Preview first 10 rows"):
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

    st.markdown("---")

    # CTA
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        st.markdown("")
        if st.button("✦ Explore Deep Insights →", type="primary", use_container_width=True):
            st.session_state.screen = "chat"
            st.session_state.chat_history = []
            st.session_state.llm_history = []
            st.rerun()
        st.markdown("")
        if st.button("↩ Upload Different File", use_container_width=True, type="secondary"):
            for k in ["screen","db_mode","csv_path","schema","df_preview","filename","chat_history","llm_history"]:
                st.session_state[k] = None if k != "screen" else "upload"
                if k in ["chat_history", "llm_history"]:
                    st.session_state[k] = []
            st.session_state.screen = "upload"
            st.rerun()


# ─────────────────────────────────────────────
# SCREEN 3: DEEP INSIGHTS CHAT
# ─────────────────────────────────────────────
elif st.session_state.screen == "chat":

    kpis_str = load_kpis()

    # Nav
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:16px; padding-bottom:20px;
                border-bottom:1px solid rgba(255,255,255,0.06); margin-bottom:32px; max-width:960px; margin-left:auto; margin-right:auto;">
        <div style="font-family:'Syne',sans-serif; font-size:18px; font-weight:700; color:#6346ff;">DataMind ✦</div>
        <div style="font-family:'Syne',sans-serif; font-size:16px; font-weight:600; color:#c8c5e8;">Deep Insights</div>
        <div style="margin-left:auto; background:rgba(0,210,190,0.1); border:1px solid rgba(0,210,190,0.25);
                    color:#00d2be; padding:5px 14px; border-radius:20px; font-size:12px;">
            📄 {st.session_state.filename}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Back button
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Overview", type="secondary"):
            st.session_state.screen = "overview"
            st.rerun()

    st.markdown("<div style='max-width:960px; margin:0 auto;'>", unsafe_allow_html=True)

    # Suggestion chips as buttons
    if not st.session_state.chat_history:
        st.markdown("""
        <div style="margin: 8px 0 4px; color:#5e5c78; font-size:12px; letter-spacing:0.08em; text-transform:uppercase;">
            Try asking
        </div>
        """, unsafe_allow_html=True)

        suggestions = [
            "Show revenue trend by month",
            "Top 10 customers by spend",
            "Which category has most sales?",
            "Average order value",
            "Sales by country on a map",
        ]
        cols = st.columns(len(suggestions))
        for i, s in enumerate(suggestions):
            with cols[i]:
                if st.button(s, key=f"sugg_{i}", use_container_width=True, type="secondary"):
                    st.session_state["prefill"] = s
                    st.rerun()

    # Render history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            with st.container():
                if msg.get("sql"):
                    with st.expander("🔍 Generated SQL", expanded=False):
                        st.code(msg["sql"], language="sql")
                if msg.get("df") is not None and not msg["df"].empty:
                    tab1, tab2, tab3 = st.tabs(["📊 Results", "📈 Chart", "🧠 Analysis"])
                    with tab1:
                        st.dataframe(msg["df"], use_container_width=True, hide_index=True)
                        st.caption(f"{len(msg['df']):,} rows")
                        st.download_button(
                            "⬇️ Export CSV", msg["df"].to_csv(index=False),
                            file_name="results.csv", mime="text/csv",
                            key=f"dl_{msg.get('id', id(msg))}",
                        )
                    with tab2:
                        fig = auto_chart(msg["df"].copy(), title=msg.get("question",""))
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No chart available for this shape of data.")
                    with tab3:
                        if msg.get("explanation"):
                            st.markdown(msg["explanation"])
                if msg.get("warnings"):
                    for w in msg["warnings"]:
                        st.warning(w)
                if msg.get("error"):
                    st.error(msg["error"])
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Chat input
    prefill = st.session_state.pop("prefill", "")
    question = st.chat_input("Ask anything about your data...") or prefill

    if question:
        if not st.session_state.schema:
            st.warning("No data loaded.")
            st.stop()

        st.session_state.chat_history.append({"role": "user", "content": question})

        sql = None
        df_result = None
        explanation = None
        warnings = []
        error = None

        with st.spinner("Thinking..."):
            try:
                raw_sql = generate_sql(
                    question=question,
                    schema=st.session_state.schema,
                    kpis=kpis_str,
                    history=st.session_state.llm_history,
                )
                sql = validate_sql(raw_sql)
            except GuardrailError as e:
                error = f"🚫 {e}"
            except Exception as e:
                error = f"❌ SQL generation failed: {e}"

        if sql and not error:
            with st.spinner("Running query..."):
                try:
                    df_result = run_query(sql)
                except Exception as e:
                    with st.spinner("Auto-fixing query..."):
                        try:
                            fixed = fix_sql(question, st.session_state.schema, sql, str(e))
                            sql = validate_sql(fixed)
                            df_result = run_query(sql)
                        except Exception as e2:
                            error = f"❌ Query failed: {e2}"

        if df_result is not None and not df_result.empty:
            warnings = run_validations(df_result, sql)
            with st.spinner("Analyzing..."):
                try:
                    explanation = explain_results(
                        question=question, sql=sql,
                        columns=df_result.columns.tolist(),
                        sample_rows=df_result.head(5).to_string(index=False),
                        row_count=len(df_result),
                    )
                except Exception:
                    explanation = None

        # Update LLM history
        if sql:
            st.session_state.llm_history.append({"role": "user", "content": question})
            st.session_state.llm_history.append({"role": "assistant", "content": f"```sql\n{sql}\n```"})
            st.session_state.llm_history = st.session_state.llm_history[-20:]

        st.session_state.chat_history.append({
            "role": "assistant",
            "question": question,
            "sql": sql,
            "df": df_result,
            "explanation": explanation,
            "warnings": warnings,
            "error": error,
            "id": len(st.session_state.chat_history),
        })
        st.rerun()
