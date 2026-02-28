"""
validators.py - Post-execution data quality and analytics sanity checks.
Warns the user about potential issues like double-counting or join explosions.
"""

import pandas as pd


def run_validations(df: pd.DataFrame, sql: str) -> list[str]:
    """
    Run a suite of post-execution validation checks.

    Returns:
        List of warning strings (empty = all clear)
    """
    warnings = []

    if df.empty:
        warnings.append("⚠️ Query returned 0 rows. Check your filters or date ranges.")
        return warnings

    warnings += _check_nulls(df)
    warnings += _check_row_explosion(df, sql)
    warnings += _check_duplicate_keys(df)
    warnings += _check_outliers(df)
    warnings += _check_mixed_grain(df)

    return warnings


def _check_nulls(df: pd.DataFrame) -> list[str]:
    """Warn if key columns have high null rates."""
    warnings = []
    for col in df.columns:
        null_pct = df[col].isna().mean()
        if null_pct > 0.3:
            warnings.append(
                f"⚠️ Column `{col}` is {null_pct:.0%} null. "
                "Results may be incomplete — check your JOIN or filter logic."
            )
    return warnings


def _check_row_explosion(df: pd.DataFrame, sql: str) -> list[str]:
    """Warn if a JOIN likely caused a row explosion (many-to-many)."""
    warnings = []
    row_count = len(df)
    join_count = sql.upper().count("JOIN")

    if join_count >= 2 and row_count > 500:
        warnings.append(
            f"⚠️ Query uses {join_count} JOINs and returned {row_count:,} rows. "
            "Possible many-to-many join explosion — verify row grain."
        )
    return warnings


def _check_duplicate_keys(df: pd.DataFrame) -> list[str]:
    """Warn if what looks like an ID column has duplicates."""
    warnings = []
    id_cols = [c for c in df.columns if c.lower().endswith("id") or c.lower() == "id"]
    for col in id_cols[:1]:  # Check first ID-like column only
        if df[col].duplicated().any():
            dup_count = df[col].duplicated().sum()
            warnings.append(
                f"⚠️ Column `{col}` has {dup_count:,} duplicate values. "
                "If this is a primary key, your query may be double-counting."
            )
    return warnings


def _check_outliers(df: pd.DataFrame) -> list[str]:
    """Warn if a numeric column has extreme outliers."""
    warnings = []
    numeric_cols = df.select_dtypes(include="number").columns

    for col in numeric_cols[:3]:  # Check first 3 numeric cols
        series = df[col].dropna()
        if len(series) < 5:
            continue
        p99 = series.quantile(0.99)
        median = series.median()
        if median > 0 and p99 > median * 50:
            warnings.append(
                f"⚠️ Column `{col}` has extreme outliers "
                f"(p99 = {p99:,.0f} vs median = {median:,.0f}). "
                "Consider filtering or investigating these records."
            )
    return warnings


def _check_mixed_grain(df: pd.DataFrame) -> list[str]:
    """Warn if both daily and monthly date-like columns appear together."""
    warnings = []
    col_names = [c.lower() for c in df.columns]
    has_daily = any("date" in c or "day" in c for c in col_names)
    has_monthly = any("month" in c or "year" in c for c in col_names)

    if has_daily and has_monthly:
        warnings.append(
            "⚠️ Query result contains both daily and monthly time dimensions. "
            "Mixed grain may cause incorrect aggregations."
        )
    return warnings
