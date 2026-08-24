from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def compute_correlations(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Compute Pearson correlation matrix for numeric columns."""
    numeric = dataframe.select_dtypes(include="number")
    if numeric.empty or len(numeric.columns) < 2:
        return pd.DataFrame()
    return numeric.corr()


def find_strong_correlations(corr_matrix: pd.DataFrame, threshold: float = 0.7) -> list[tuple[str, str, float]]:
    """Find pairs of columns with high correlation (excluding self-correlation)."""
    strong = []
    for i, col1 in enumerate(corr_matrix.columns):
        for col2 in corr_matrix.columns[i + 1 :]:
            corr_value = corr_matrix.loc[col1, col2]
            if abs(corr_value) >= threshold:
                strong.append((col1, col2, float(corr_value)))
    return sorted(strong, key=lambda x: abs(x[2]), reverse=True)


def segment_by_column(dataframe: pd.DataFrame, column: str) -> dict[str, pd.DataFrame]:
    """Segment dataset by unique values in a column."""
    if column not in dataframe.columns:
        return {}
    segments = {}
    for value in dataframe[column].unique():
        segments[f"{column}={value}"] = dataframe[dataframe[column] == value]
    return segments


def sample_data(dataframe: pd.DataFrame, sample_size: int | None = None, fraction: float | None = None, random_state: int = 42) -> pd.DataFrame:
    """
    Draw a random sample from the dataset.
    Either sample_size (absolute) or fraction (0.0-1.0) can be used.
    """
    if sample_size and sample_size > 0:
        return dataframe.sample(n=min(sample_size, len(dataframe)), random_state=random_state)
    elif fraction and 0 < fraction <= 1:
        return dataframe.sample(frac=fraction, random_state=random_state)
    return dataframe


def build_validation_rule(rule_name: str, column: str, rule_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Define a data validation rule (doesn't execute, just stores the rule)."""
    return {"name": rule_name, "column": column, "type": rule_type, "params": params}


def execute_validation(dataframe: pd.DataFrame, rule: dict[str, Any]) -> tuple[bool, int]:
    """
    Execute a validation rule and return (passed, violations_count).
    
    Rule types: 'not_null', 'range', 'pattern', 'unique', 'enum', 'custom_numeric'
    """
    column = rule["column"]
    if column not in dataframe.columns:
        return False, len(dataframe)

    violations = 0

    if rule["type"] == "not_null":
        violations = int(dataframe[column].isna().sum())

    elif rule["type"] == "range":
        min_val = rule["params"].get("min")
        max_val = rule["params"].get("max")
        numeric_col = pd.to_numeric(dataframe[column], errors="coerce")
        if min_val is not None:
            violations += int((numeric_col < min_val).sum())
        if max_val is not None:
            violations += int((numeric_col > max_val).sum())

    elif rule["type"] == "pattern":
        import re

        pattern = rule["params"].get("pattern", "")
        violations = int(dataframe[column].astype(str).str.contains(pattern, na=False, regex=True).sum() == 0)

    elif rule["type"] == "unique":
        violations = len(dataframe[column]) - len(dataframe[column].unique())

    elif rule["type"] == "enum":
        allowed = rule["params"].get("allowed", [])
        violations = int((~dataframe[column].isin(allowed)).sum())

    elif rule["type"] == "custom_numeric":
        operator = rule["params"].get("operator", ">")
        threshold = rule["params"].get("threshold", 0)
        numeric_col = pd.to_numeric(dataframe[column], errors="coerce")
        if operator == ">":
            violations = int((numeric_col <= threshold).sum())
        elif operator == "<":
            violations = int((numeric_col >= threshold).sum())
        elif operator == ">=":
            violations = int((numeric_col < threshold).sum())
        elif operator == "<=":
            violations = int((numeric_col > threshold).sum())

    passed = violations == 0
    return passed, violations


def data_quality_score(dataframe: pd.DataFrame, profile: dict[str, Any]) -> float:
    """
    Compute an overall data quality score (0.0 to 1.0) based on completeness and uniqueness.
    
    Score components:
    - Completeness: (1 - missing_fraction) * 0.6
    - Uniqueness: (1 - duplicate_fraction) * 0.4
    """
    total_cells = len(dataframe) * len(dataframe.columns)
    missing_cells = profile.get("missing_cells", 0)
    duplicate_rows = profile.get("duplicate_rows", 0)

    completeness = 1.0 - (missing_cells / total_cells) if total_cells > 0 else 1.0
    uniqueness = 1.0 - (duplicate_rows / len(dataframe)) if len(dataframe) > 0 else 1.0

    score = (completeness * 0.6) + (uniqueness * 0.4)
    return min(max(score, 0.0), 1.0)  # Clamp to [0, 1]


def generate_quality_summary(dataframe: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    """Generate a comprehensive quality summary with actionable insights."""
    score = data_quality_score(dataframe, profile)
    quality_grade = "A" if score >= 0.9 else "B" if score >= 0.75 else "C" if score >= 0.6 else "D"

    issues = []
    if profile.get("missing_cells", 0) > 0:
        issues.append(f"Missing values: {profile['missing_cells']} cells")
    if profile.get("duplicate_rows", 0) > 0:
        issues.append(f"Duplicate rows: {profile['duplicate_rows']}")
    if profile.get("outliers", pd.Series()).sum() > 0:
        issues.append(f"Outliers detected: {int(profile['outliers'].sum())} cells")

    return {
        "quality_score": float(score),
        "quality_grade": quality_grade,
        "total_issues": len(issues),
        "issues": issues,
        "completeness": 1.0 - (profile.get("missing_cells", 0) / (len(dataframe) * len(dataframe.columns))),
        "uniqueness": 1.0 - (profile.get("duplicate_rows", 0) / len(dataframe)),
    }
