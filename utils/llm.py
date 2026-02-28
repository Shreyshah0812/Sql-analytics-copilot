"""
llm.py - All Claude API interactions for the SQL Copilot.
Handles SQL generation, auto-fix on error, and result explanation.
"""

import os
import anthropic
from pathlib import Path
import streamlit as st

api_key = st.secrets.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)

MODEL = "claude-sonnet-4-6"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = Path("prompts") / filename
    return path.read_text()


def generate_sql(question: str, schema: str, kpis: str, history: list[dict] = None) -> str:
    """
    Generate SQL from a natural language question.

    Args:
        question: User's natural language question
        schema: Database schema string
        kpis: KPI definitions string
        history: Optional list of prior {role, content} messages for follow-ups

    Returns:
        Raw SQL string (or ERROR: <reason>)
    """
    system_prompt = _load_prompt("sql_gen.txt").format(schema=schema, kpis=kpis)

    messages = (history or []) + [{"role": "user", "content": question}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text.strip()


def fix_sql(question: str, schema: str, failed_sql: str, error_msg: str) -> str:
    """
    Ask Claude to fix a SQL query that failed with an error.

    Returns:
        Corrected SQL string
    """
    prompt = _load_prompt("sql_fix.txt").format(
        schema=schema,
        question=question,
        sql=failed_sql,
        error=error_msg,
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def explain_results(question: str, sql: str, columns: list, sample_rows: str, row_count: int) -> str:
    """
    Generate an analyst-style explanation of query results.

    Returns:
        Markdown-formatted explanation string
    """
    prompt = _load_prompt("sql_explain.txt").format(
        question=question,
        sql=sql,
        columns=", ".join(columns),
        sample_rows=sample_rows,
        row_count=row_count,
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
