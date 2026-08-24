from __future__ import annotations

import re
from typing import Any

import pandas as pd


def validate_sql_query(query: str) -> tuple[bool, str | None]:
    """
    Validate that a SQL query is read-only and safe.
    Only allows SELECT statements; blocks mutations (INSERT, UPDATE, DELETE, DROP, etc.).
    """
    query_upper = query.strip().upper()

    # Must start with SELECT
    if not query_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed (read-only)."

    # Block dangerous keywords
    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE", "PRAGMA", ";DROP", ";DELETE"]
    for keyword in dangerous_keywords:
        if keyword in query_upper:
            return False, f"Operation '{keyword}' is not allowed."

    # Block multiple statements (semicolon separation)
    if query.rstrip(";").count(";") > 0:
        return False, "Multiple statements are not allowed."

    return True, None


def execute_safe_sql(dataframe: pd.DataFrame, query: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Execute a validated read-only SQL query on an in-memory dataframe.
    Uses pandas.read_sql with an in-memory SQLite connection.
    Returns (result_dataframe, error_message).
    """
    valid, error = validate_sql_query(query)
    if not valid:
        return None, error

    try:
        import sqlite3

        conn = sqlite3.connect(":memory:")
        dataframe.to_sql("data", conn, if_exists="replace", index=False)

        result = pd.read_sql(query, conn)
        conn.close()
        return result, None

    except pd.errors.DatabaseError as e:
        return None, f"Database error: {str(e)}"
    except Exception as e:
        return None, f"Query execution failed: {str(e)}"


def build_query_hint(dataframe: pd.DataFrame) -> str:
    """Generate a helpful query hint based on dataframe schema."""
    columns = ", ".join(f"'{col}'" for col in dataframe.columns)
    hint = f"Available columns: {columns}\nExample: SELECT * FROM data LIMIT 10"
    return hint


def suggest_queries(dataframe: pd.DataFrame) -> list[str]:
    """Suggest common read-only queries based on dataframe schema."""
    numeric_cols = dataframe.select_dtypes(include="number").columns.tolist()
    categorical_cols = dataframe.select_dtypes(exclude="number").columns.tolist()

    suggestions = [
        "SELECT * FROM data LIMIT 10",
        f"SELECT COUNT(*) as row_count FROM data",
        f"SELECT COUNT(DISTINCT source_file) as unique_files FROM data" if "source_file" in dataframe.columns else None,
    ]

    if numeric_cols:
        col = numeric_cols[0]
        suggestions.extend(
            [
                f"SELECT {col}, COUNT(*) as count FROM data GROUP BY {col} LIMIT 10",
                f"SELECT AVG({col}) as average, MIN({col}) as minimum, MAX({col}) as maximum FROM data",
            ]
        )

    if categorical_cols:
        col = categorical_cols[0]
        suggestions.append(f"SELECT {col}, COUNT(*) as frequency FROM data GROUP BY {col} ORDER BY frequency DESC LIMIT 10")

    return [s for s in suggestions if s is not None]


def query_to_dataframe(result: pd.DataFrame | None) -> dict[str, Any]:
    """Format query result for display."""
    if result is None:
        return {"rows": 0, "columns": 0, "data": None}

    return {"rows": len(result), "columns": len(result.columns), "data": result}
