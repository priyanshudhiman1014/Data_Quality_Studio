from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class CleaningResult:
    dataframe: pd.DataFrame
    changes: list[str]
    errors: list[str]


def profile_dataframe(frame: pd.DataFrame) -> dict[str, Any]:
    numeric = frame.select_dtypes(include="number")
    missing = frame.isna().sum().sort_values(ascending=False)
    numeric_summary = numeric.describe().T if not numeric.empty else pd.DataFrame()
    categorical_summary = (
        frame.select_dtypes(exclude="number").nunique().sort_values(ascending=False).to_frame("unique_values")
        if not frame.select_dtypes(exclude="number").empty
        else pd.DataFrame()
    )
    outliers: dict[str, int] = {}
    for column in numeric.columns:
        values = numeric[column].dropna()
        if values.empty:
            outliers[column] = 0
            continue
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        outliers[column] = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())

    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "duplicate_rows": int(frame.duplicated().sum()),
        "missing_cells": int(frame.isna().sum().sum()),
        "missing_by_column": missing[missing > 0],
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "outliers": pd.Series(outliers, name="outlier_count").sort_values(ascending=False),
    }


def clean_dataframe(
    frame: pd.DataFrame,
    missing_strategy: str = "median",
    remove_duplicates: bool = True,
    trim_text: bool = True,
) -> CleaningResult:
    cleaned = frame.copy()
    changes: list[str] = []
    errors: list[str] = []

    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    if len(set(cleaned.columns)) != len(cleaned.columns):
        seen: dict[str, int] = {}
        unique_columns: list[str] = []
        for column in cleaned.columns:
            occurrence = seen.get(column, 0)
            unique_columns.append(column if occurrence == 0 else f"{column}.{occurrence}")
            seen[column] = occurrence + 1
        cleaned.columns = unique_columns
        changes.append("Renamed duplicate column names")

    if trim_text:
        text_columns = cleaned.select_dtypes(include=["object", "string"]).columns
        for column in text_columns:
            cleaned[column] = cleaned[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        if len(text_columns):
            changes.append(f"Trimmed whitespace in {len(text_columns)} text column(s)")

    before_duplicates = len(cleaned)
    if remove_duplicates:
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
        removed = before_duplicates - len(cleaned)
        if removed:
            changes.append(f"Removed {removed} duplicate row(s)")

    missing_columns = cleaned.columns[cleaned.isna().any()].tolist()
    if missing_columns:
        if missing_strategy == "drop_rows":
            before = len(cleaned)
            cleaned = cleaned.dropna().reset_index(drop=True)
            changes.append(f"Dropped {before - len(cleaned)} row(s) containing missing values")
        elif missing_strategy in {"median", "mean", "mode", "zero"}:
            for column in missing_columns:
                series = cleaned[column]
                if missing_strategy == "zero" and pd.api.types.is_numeric_dtype(series):
                    fill_value = 0
                elif missing_strategy == "median" and pd.api.types.is_numeric_dtype(series):
                    fill_value = series.median()
                elif missing_strategy == "mean" and pd.api.types.is_numeric_dtype(series):
                    fill_value = series.mean()
                else:
                    modes = series.mode(dropna=True)
                    fill_value = modes.iloc[0] if not modes.empty else "Unknown"
                cleaned[column] = series.fillna(fill_value)
            changes.append(f"Filled missing values using {missing_strategy}")
        else:
            errors.append(f"Unsupported missing-value strategy: {missing_strategy}")

    cleaned = cleaned.convert_dtypes()
    return CleaningResult(cleaned, changes, errors)


def improve_dataframe(
    frame: pd.DataFrame,
    standardize_columns: bool = False,
    text_case: str = "Keep original",
    parse_dates: bool = False,
    remove_empty: bool = False,
) -> CleaningResult:
    """Apply optional quality improvements after the core cleaning step."""
    improved = frame.copy()
    changes: list[str] = []
    errors: list[str] = []

    if remove_empty:
        empty_columns = improved.columns[improved.isna().all()].tolist()
        if empty_columns:
            improved = improved.drop(columns=empty_columns)
            changes.append(f"Removed {len(empty_columns)} completely empty column(s)")
        before_rows = len(improved)
        improved = improved.dropna(how="all").reset_index(drop=True)
        if before_rows != len(improved):
            changes.append(f"Removed {before_rows - len(improved)} completely empty row(s)")

    if standardize_columns:
        renamed: list[str] = []
        seen: dict[str, int] = {}
        for index, column in enumerate(improved.columns):
            normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(column).strip().lower()).strip("_")
            normalized = normalized or f"column_{index + 1}"
            occurrence = seen.get(normalized, 0)
            renamed.append(normalized if occurrence == 0 else f"{normalized}_{occurrence + 1}")
            seen[normalized] = occurrence + 1
        if list(improved.columns) != renamed:
            improved.columns = renamed
            changes.append("Standardized column names to lowercase snake_case")

    text_columns = improved.select_dtypes(include=["object", "string"]).columns
    if text_case != "Keep original":
        for column in text_columns:
            values = improved[column].map(lambda value: value.strip() if isinstance(value, str) else value)
            if text_case == "lowercase":
                improved[column] = values.map(lambda value: value.lower() if isinstance(value, str) else value)
            elif text_case == "Title Case":
                improved[column] = values.map(lambda value: value.title() if isinstance(value, str) else value)
        if len(text_columns):
            changes.append(f"Applied {text_case} to {len(text_columns)} text column(s)")

    if parse_dates:
        converted_columns: list[str] = []
        for column in improved.select_dtypes(include=["object", "string"]).columns:
            series = improved[column]
            non_empty = series.dropna()
            if non_empty.empty:
                continue
            converted = pd.to_datetime(series, errors="coerce", format="mixed")
            if converted.notna().sum() / len(non_empty) >= 0.8:
                improved[column] = converted
                converted_columns.append(str(column))
        if converted_columns:
            changes.append(f"Parsed {len(converted_columns)} date-like column(s)")

    return CleaningResult(improved.convert_dtypes(), changes, errors)


def prepare_csv_export(frame: pd.DataFrame) -> pd.DataFrame:
    """Prevent exported CSV cells from being interpreted as spreadsheet formulas."""
    exported = frame.copy()
    dangerous_prefixes = ("=", "+", "-", "@")
    for column in exported.select_dtypes(include=["object", "string"]).columns:
        exported[column] = exported[column].map(
            lambda value: f"'{value}" if isinstance(value, str) and value.startswith(dangerous_prefixes) else value
        )
    return exported


def run_hypothesis_test(
    frame: pd.DataFrame,
    test_name: str,
    column: str,
    reference_value: float = 0.0,
    group_column: str | None = None,
    group_a: str | None = None,
    group_b: str | None = None,
    second_column: str | None = None,
) -> dict[str, Any]:
    if column not in frame.columns:
        raise ValueError("Selected column does not exist")

    if test_name == "One-sample t-test":
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if len(values) < 2:
            raise ValueError("At least two numeric observations are required")
        result = stats.ttest_1samp(values, reference_value)
        return _test_result(test_name, result.statistic, result.pvalue, f"H0: mean({column}) = {reference_value}")

    if test_name == "Shapiro-Wilk normality test":
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if not 3 <= len(values) <= 5000:
            raise ValueError("Shapiro-Wilk requires between 3 and 5,000 observations")
        result = stats.shapiro(values)
        return _test_result(test_name, result.statistic, result.pvalue, f"H0: {column} is normally distributed")

    if test_name == "Independent two-group t-test":
        if not group_column or group_column not in frame.columns or group_a is None or group_b is None:
            raise ValueError("Choose a grouping column and two groups")
        values_a = pd.to_numeric(frame.loc[frame[group_column] == group_a, column], errors="coerce").dropna()
        values_b = pd.to_numeric(frame.loc[frame[group_column] == group_b, column], errors="coerce").dropna()
        if len(values_a) < 2 or len(values_b) < 2:
            raise ValueError("Each group needs at least two numeric observations")
        result = stats.ttest_ind(values_a, values_b, equal_var=False)
        hypothesis = f"H0: mean({column}|{group_a}) = mean({column}|{group_b})"
        return _test_result(test_name, result.statistic, result.pvalue, hypothesis)

    if test_name == "Chi-square independence test":
        if not second_column or second_column not in frame.columns:
            raise ValueError("Choose a second categorical column")
        table = pd.crosstab(frame[column], frame[second_column])
        if table.shape[0] < 2 or table.shape[1] < 2:
            raise ValueError("Both categorical columns need at least two distinct values")
        result = stats.chi2_contingency(table)
        return _test_result(test_name, result[0], result[1], f"H0: {column} and {second_column} are independent")

    raise ValueError("Unsupported hypothesis test")


def _test_result(name: str, statistic: float, pvalue: float, null_hypothesis: str) -> dict[str, Any]:
    alpha = 0.05
    return {
        "test": name,
        "statistic": float(statistic),
        "p_value": float(pvalue),
        "alpha": alpha,
        "decision": "Reject H0" if pvalue < alpha else "Fail to reject H0",
        "null_hypothesis": null_hypothesis,
    }
