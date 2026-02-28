"""
app.py - SQL + Analytics Copilot
Main Streamlit application.
"""

import os
import tempfile
import yaml
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

from utils.db import (
    get_sqlite_schema, run_sqlite_query,
    get_csv_schema, run_csv_query,
    seed_sample_db,
)
from utils.llm import generate_sql, fix_sql, explain_results
from utils.guardrails import validate_sql, GuardrailError
from utils.charts import auto_chart
from utils.validators import run_validations

load_dotenv()

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SQL + Analytics Copilot",
    page_icon="🧠",
    layout="wide",
)

# ─────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────
def init_state():
    defaults = {
        "chat_history": [],       # [{role, content}] for display
        "llm_history": [],        # [{role, content}] passed to LLM
        "last_sql": "",
        "last_df": None,
        "db_mode": "sample",      # "sample" | "csv"
        "csv_path": None,
        "schema": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─────────────────────────────────────────────
# Load KPIs
# ─────────────────────────────────────────────
@st.cache_data
def load_kpis() -> str:
    kpi_path = Path("metrics/kpis.yaml")
    if not kpi_path.exists():
        return "No KPI definitions found."
    with open(kpi_path) as f:
        kpis = yaml.safe_load(f)
    lines = []
    for name, info in kpis.items():
        if isinstance(info, dict):
            lines.append(f"- {name}: {info.get('definition', '')}  # {info.get('description', '')}")
        else:
            lines.append(f"- {name}: {info}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🧠 SQL Copilot")
    st.markdown("**Data source**")

    db_choice = st.radio(
        "Connect to:",
        ["Sample DB (Chinook-style)", "Upload a CSV file"],
        key="db_choice_radio",
    )

    if db_choice == "Sample DB (Chinook-style)":
        st.session_state.db_mode = "sample"
        seed_sample_db("db/sample.db")
        schema = get_sqlite_schema("db/sample.db")
        st.session_state.schema = schema

    else:
        st.session_state.db_mode = "csv"
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            tmp.write(uploaded_file.read())
            tmp.flush()
            st.session_state.csv_path = tmp.name
            schema = get_csv_schema(tmp.name)
            st.session_state.schema = schema
            st.success(f"Loaded: {uploaded_file.name}")

    # Schema viewer
    if st.session_state.schema:
        with st.expander("📋 View Schema", expanded=False):
            st.code(st.session_state.schema, language="text")

    st.divider()

    # KPI viewer
    kpis_str = load_kpis()
    with st.expander("📐 KPI Definitions", expanded=False):
        st.code(kpis_str, language="yaml")

    st.divider()

    # Example questions
    st.markdown("**💡 Try asking:**")
    example_questions = [
        "Revenue trend by month",
        "Top 10 customers by total spend",
        "Revenue by country",
        "Average order value",
        "Which genres are most popular?",
    ]
    for q in example_questions:
        if st.button(q, use_container_width=True):
            st.session_state["prefill_question"] = q

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.llm_history = []
        st.session_state.last_sql = ""
        st.session_state.last_df = None
        st.rerun()


# ─────────────────────────────────────────────
# Main area
# ─────────────────────────────────────────────
st.title("🧠 SQL + Analytics Copilot")
st.caption("Ask questions in plain English. Get SQL, results, charts, and analysis.")

# Render chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            # Structured assistant response
            if "sql" in msg:
                with st.expander("🔍 Generated SQL", expanded=True):
                    st.code(msg["sql"], language="sql")
            if "df" in msg and msg["df"] is not None:
                df = msg["df"]
                tab1, tab2, tab3 = st.tabs(["📊 Results", "📈 Chart", "🧠 Explanation"])
                with tab1:
                    st.dataframe(df, use_container_width=True)
                    st.caption(f"{len(df):,} rows returned")
                    st.download_button(
                        "⬇️ Download CSV",
                        data=df.to_csv(index=False),
                        file_name="results.csv",
                        mime="text/csv",
                        key=f"dl_{msg.get('id', id(msg))}",
                    )
                with tab2:
                    fig = auto_chart(df.copy(), title=msg.get("question", ""))
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No chart available for this result shape.")
                with tab3:
                    if "explanation" in msg:
                        st.markdown(msg["explanation"])
                    else:
                        st.info("No explanation generated.")
            if "warnings" in msg and msg["warnings"]:
                for w in msg["warnings"]:
                    st.warning(w)
            if "error" in msg:
                st.error(msg["error"])
        else:
            st.markdown(msg["content"])


# ─────────────────────────────────────────────
# Chat input
# ─────────────────────────────────────────────
prefill = st.session_state.pop("prefill_question", "")
question = st.chat_input(
    "Ask anything about your data...",
) or prefill

if question:
    if not st.session_state.schema:
        st.warning("Please connect to a data source in the sidebar first.")
        st.stop()

    # Show user message
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Build assistant response
    with st.chat_message("assistant"):
        sql = None
        df = None
        explanation = None
        warnings = []
        error = None

        with st.spinner("Generating SQL..."):
            try:
                raw_sql = generate_sql(
                    question=question,
                    schema=st.session_state.schema,
                    kpis=kpis_str,
                    history=st.session_state.llm_history,
                )
                sql = validate_sql(raw_sql)
            except GuardrailError as e:
                error = f"🚫 Guardrail blocked this query: {e}"
            except Exception as e:
                error = f"❌ SQL generation failed: {e}"

        if sql and not error:
            with st.expander("🔍 Generated SQL", expanded=True):
                st.code(sql, language="sql")

            with st.spinner("Running query..."):
                try:
                    if st.session_state.db_mode == "sample":
                        df = run_sqlite_query("db/sample.db", sql)
                    else:
                        df = run_csv_query(st.session_state.csv_path, sql)
                except Exception as e:
                    # Auto-fix loop
                    with st.spinner("Query failed — asking Claude to fix it..."):
                        try:
                            fixed_sql = fix_sql(
                                question=question,
                                schema=st.session_state.schema,
                                failed_sql=sql,
                                error_msg=str(e),
                            )
                            fixed_sql = validate_sql(fixed_sql)
                            sql = fixed_sql
                            st.info("🔧 Auto-fixed SQL:")
                            st.code(sql, language="sql")
                            if st.session_state.db_mode == "sample":
                                df = run_sqlite_query("db/sample.db", sql)
                            else:
                                df = run_csv_query(st.session_state.csv_path, sql)
                        except Exception as e2:
                            error = f"❌ Query failed even after auto-fix: {e2}"

        if df is not None and not df.empty:
            warnings = run_validations(df, sql)

            tab1, tab2, tab3 = st.tabs(["📊 Results", "📈 Chart", "🧠 Explanation"])

            with tab1:
                st.dataframe(df, use_container_width=True)
                st.caption(f"{len(df):,} rows returned")
                st.download_button(
                    "⬇️ Download CSV",
                    data=df.to_csv(index=False),
                    file_name="results.csv",
                    mime="text/csv",
                )

            with tab2:
                fig = auto_chart(df.copy(), title=question)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No chart available for this result shape.")

            with tab3:
                with st.spinner("Analyzing results..."):
                    try:
                        sample = df.head(5).to_string(index=False)
                        explanation = explain_results(
                            question=question,
                            sql=sql,
                            columns=df.columns.tolist(),
                            sample_rows=sample,
                            row_count=len(df),
                        )
                        st.markdown(explanation)
                    except Exception as e:
                        st.warning(f"Explanation unavailable: {e}")

            for w in warnings:
                st.warning(w)

        elif df is not None and df.empty:
            st.info("✅ Query ran successfully but returned 0 rows.")

        if error:
            st.error(error)

    # Update LLM conversation history for follow-ups
    if sql:
        st.session_state.llm_history.append({"role": "user", "content": question})
        st.session_state.llm_history.append({
            "role": "assistant",
            "content": f"```sql\n{sql}\n```"
        })
        # Keep context window reasonable (last 10 turns)
        st.session_state.llm_history = st.session_state.llm_history[-20:]

    # Save to display history
    st.session_state.chat_history.append({
        "role": "assistant",
        "question": question,
        "sql": sql,
        "df": df,
        "explanation": explanation,
        "warnings": warnings,
        "error": error,
        "id": len(st.session_state.chat_history),
    })
