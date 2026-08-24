from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditStore:
    def __init__(self, database_path: str | Path = "data_quality.db") -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS audit_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    original_rows INTEGER NOT NULL,
                    cleaned_rows INTEGER NOT NULL,
                    original_columns INTEGER NOT NULL,
                    cleaned_columns INTEGER NOT NULL,
                    changes_json TEXT NOT NULL,
                    quality_json TEXT NOT NULL
                )
            """)

    def save_run(self, dataset_name: str, original: dict[str, Any], cleaned: dict[str, Any], changes: list[str]) -> None:
        quality = {
            "missing_cells": original.get("missing_cells", 0),
            "duplicate_rows": original.get("duplicate_rows", 0),
            "cleaned_missing_cells": cleaned.get("missing_cells", 0),
            "cleaned_duplicate_rows": cleaned.get("duplicate_rows", 0),
        }
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO audit_runs (dataset_name, created_at, original_rows, cleaned_rows, original_columns, cleaned_columns, changes_json, quality_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dataset_name, datetime.now(timezone.utc).isoformat(), original["rows"], cleaned["rows"], original["columns"], cleaned["columns"], json.dumps(changes), json.dumps(quality)),
            )

    def recent_runs(self, limit: int = 10) -> list[tuple[Any, ...]]:
        with sqlite3.connect(self.database_path) as connection:
            return connection.execute("SELECT dataset_name, created_at, original_rows, cleaned_rows, changes_json FROM audit_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
