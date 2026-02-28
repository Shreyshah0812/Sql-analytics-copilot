"""
guardrails.py - SQL safety validation layer.
Blocks dangerous queries and enforces safe defaults before execution.
"""

import re

# Dangerous SQL keywords that should never be executed
BLOCKED_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "PRAGMA", "ATTACH", "DETACH", "VACUUM",
    "CREATE", "REPLACE", "MERGE", "EXEC", "EXECUTE",
]

MAX_LIMIT = 1000
DEFAULT_LIMIT = 100


class GuardrailError(Exception):
    """Raised when a query fails safety checks."""
    pass


def validate_sql(sql: str) -> str:
    """
    Validate and sanitize SQL before execution.

    Args:
        sql: Raw SQL string from LLM

    Returns:
        Sanitized SQL (with LIMIT enforced)

    Raises:
        GuardrailError: If query is unsafe
    """
    sql = sql.strip().rstrip(";")

    # Check for LLM error signal
    if sql.upper().startswith("ERROR:"):
        raise GuardrailError(f"LLM could not answer: {sql[6:].strip()}")

    # Strip markdown code fences if LLM included them
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip()

    # Must start with SELECT or WITH (CTEs)
    normalized = sql.upper().lstrip()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        raise GuardrailError(
            "Only SELECT queries are allowed. This query doesn't start with SELECT or WITH."
        )

    # Block dangerous keywords (check as whole words to avoid false positives)
    for keyword in BLOCKED_KEYWORDS:
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, sql, re.IGNORECASE):
            raise GuardrailError(
                f"Blocked keyword detected: `{keyword}`. "
                "Only read-only SELECT queries are permitted."
            )

    # Enforce LIMIT
    sql = _enforce_limit(sql)

    return sql


def _enforce_limit(sql: str) -> str:
    """Add or cap LIMIT clause to prevent runaway queries."""
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)

    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > MAX_LIMIT:
            sql = re.sub(
                r"\bLIMIT\s+\d+\b",
                f"LIMIT {MAX_LIMIT}",
                sql,
                flags=re.IGNORECASE,
            )
    else:
        sql = f"{sql}\nLIMIT {DEFAULT_LIMIT}"

    return sql


def check_for_lm_error(sql: str) -> bool:
    """Returns True if the LLM returned an error signal instead of SQL."""
    return sql.strip().upper().startswith("ERROR:")
