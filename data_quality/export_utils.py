from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import pandas as pd


def prepare_csv_export(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Prevent exported CSV cells from being interpreted as spreadsheet formulas."""
    exported = dataframe.copy()
    dangerous_prefixes = ("=", "+", "-", "@")
    for column in exported.select_dtypes(include=["object", "string"]).columns:
        exported[column] = exported[column].map(
            lambda value: f"'{value}" if isinstance(value, str) and value.startswith(dangerous_prefixes) else value
        )
    return exported


def generate_combined_export(cleaned_dataframe: pd.DataFrame, original_filename: str) -> tuple[bytes, str]:
    """Generate one combined cleaned CSV with source file tracking."""
    safe_export = prepare_csv_export(cleaned_dataframe)
    csv_bytes = safe_export.to_csv(index=False).encode("utf-8")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(original_filename).stem)
    filename = f"cleaned_combined_{safe_name}.csv"
    return csv_bytes, filename


def generate_separate_exports(original_dataframe: pd.DataFrame, cleaned_dataframe: pd.DataFrame) -> list[tuple[bytes, str]]:
    """Generate separate cleaned CSVs for each original source file.
    
    Assumes original_dataframe has a 'source_file' column with original filenames.
    """
    exports = []
    
    if "source_file" not in original_dataframe.columns:
        safe_export = prepare_csv_export(cleaned_dataframe)
        csv_bytes = safe_export.to_csv(index=False).encode("utf-8")
        exports.append((csv_bytes, "cleaned_dataset.csv"))
        return exports
    
    source_files = original_dataframe["source_file"].unique()
    for source_file in source_files:
        mask = original_dataframe["source_file"] == source_file
        file_cleaned = cleaned_dataframe[mask].drop(columns=["source_file"], errors="ignore")
        
        safe_export = prepare_csv_export(file_cleaned)
        csv_bytes = safe_export.to_csv(index=False).encode("utf-8")
        
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(source_file).stem)
        filename = f"cleaned_{safe_name}.csv"
        exports.append((csv_bytes, filename))
    
    return exports


def generate_html_report(profile: dict[str, Any], cleaning_changes: list[str]) -> str:
    """Generate a standalone HTML quality report for local download."""
    numeric_summary_html = ""
    if not profile.get("numeric_summary", pd.DataFrame()).empty:
        numeric_summary_html = profile["numeric_summary"].to_html()

    missing_html = ""
    if not profile.get("missing_by_column", pd.Series()).empty:
        missing_html = profile["missing_by_column"].to_frame("missing_cells").to_html()

    changes_html = "<ul>" + "".join(f"<li>{change}</li>" for change in cleaning_changes) + "</ul>"

    html = f"""
    <html>
    <head>
        <title>Data Quality Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 2em; }}
            h1, h2 {{ color: #17221d; }}
            table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
            th, td {{ border: 1px solid #ddd; padding: 0.5em; text-align: left; }}
            th {{ background-color: #f1f6f2; }}
            .metric {{ display: inline-block; margin: 1em; padding: 1em; background: #f1f6f2; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <h1>Data Quality Report</h1>
        <div class="metric"><strong>Rows:</strong> {profile.get('rows', 0):,}</div>
        <div class="metric"><strong>Columns:</strong> {profile.get('columns', 0)}</div>
        <div class="metric"><strong>Missing cells:</strong> {profile.get('missing_cells', 0)}</div>
        <div class="metric"><strong>Duplicates:</strong> {profile.get('duplicate_rows', 0)}</div>
        
        <h2>Cleaning changes</h2>
        {changes_html}
        
        <h2>Numeric summary</h2>
        {numeric_summary_html or '<p>No numeric columns.</p>'}
        
        <h2>Missing values by column</h2>
        {missing_html or '<p>No missing values.</p>'}
    </body>
    </html>
    """
    return html
