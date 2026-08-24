from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ChatCommand:
    command_type: str
    params: dict[str, Any]
    valid: bool
    error: str | None = None


def parse_chat_command(user_input: str) -> ChatCommand:
    """Parse and validate natural-language-like data change requests."""
    user_input = user_input.strip()

    # RENAME COLUMN
    rename_match = re.match(r"rename\s+(?:column\s+)?['\"]?(\w+)['\"]?\s+to\s+['\"]?(\w+)['\"]?", user_input, re.IGNORECASE)
    if rename_match:
        old_col, new_col = rename_match.groups()
        return ChatCommand("rename", {"old_name": old_col, "new_name": new_col}, True)

    # DROP COLUMN
    drop_match = re.match(r"drop\s+(?:column\s+)?['\"]?(\w+)['\"]?", user_input, re.IGNORECASE)
    if drop_match:
        col = drop_match.group(1)
        return ChatCommand("drop", {"column": col}, True)

    # KEEP ONLY
    keep_match = re.match(r"keep\s+only\s+(.+?)(?:\s*$|\s+where)", user_input, re.IGNORECASE)
    if keep_match:
        cols_str = keep_match.group(1)
        columns = [c.strip().strip("'\"") for c in cols_str.split(",")]
        return ChatCommand("keep", {"columns": columns}, True)

    # DUPLICATE COLUMN
    dup_match = re.match(r"duplicate\s+(?:column\s+)?['\"]?(\w+)['\"]?\s+as\s+['\"]?(\w+)['\"]?", user_input, re.IGNORECASE)
    if dup_match:
        old_col, new_col = dup_match.groups()
        return ChatCommand("duplicate", {"source": old_col, "new_name": new_col}, True)

    # REMOVE ROWS WHERE (safe pattern: column operator value)
    remove_match = re.match(r"remove\s+rows?\s+where\s+(\w+)\s*(==|!=|>|<|>=|<=)\s*['\"]?(.+?)['\"]?$", user_input, re.IGNORECASE)
    if remove_match:
        column, operator, value = remove_match.groups()
        return ChatCommand("remove_where", {"column": column, "operator": operator, "value": value}, True)

    # FILL MISSING (safe pattern: column with strategy)
    fill_match = re.match(r"fill\s+missing\s+(?:in\s+)?['\"]?(\w+)['\"]?\s+with\s+(median|mean|mode|zero|forward|backward)", user_input, re.IGNORECASE)
    if fill_match:
        column, strategy = fill_match.groups()
        return ChatCommand("fill_missing", {"column": column, "strategy": strategy.lower()}, True)

    return ChatCommand("unknown", {}, False, error="Command not recognized. Try: rename, drop, keep only, duplicate, remove rows where, or fill missing.")


def apply_chat_command(dataframe: pd.DataFrame, command: ChatCommand) -> tuple[pd.DataFrame, str | None]:
    """Safely apply parsed chat command to dataframe. Returns (modified_df, error_message)."""
    if not command.valid:
        return dataframe, command.error

    try:
        if command.command_type == "rename":
            old_name = command.params["old_name"]
            new_name = command.params["new_name"]
            if old_name not in dataframe.columns:
                return dataframe, f"Column '{old_name}' not found."
            return dataframe.rename(columns={old_name: new_name}), None

        elif command.command_type == "drop":
            col = command.params["column"]
            if col not in dataframe.columns:
                return dataframe, f"Column '{col}' not found."
            return dataframe.drop(columns=[col]), None

        elif command.command_type == "keep":
            cols = command.params["columns"]
            missing = [c for c in cols if c not in dataframe.columns]
            if missing:
                return dataframe, f"Columns not found: {', '.join(missing)}"
            return dataframe[cols], None

        elif command.command_type == "duplicate":
            source = command.params["source"]
            new_name = command.params["new_name"]
            if source not in dataframe.columns:
                return dataframe, f"Column '{source}' not found."
            result = dataframe.copy()
            result[new_name] = dataframe[source]
            return result, None

        elif command.command_type == "remove_where":
            column = command.params["column"]
            operator = command.params["operator"]
            value = command.params["value"]
            if column not in dataframe.columns:
                return dataframe, f"Column '{column}' not found."
            result = dataframe.copy()
            try:
                if operator == "==":
                    result = result[result[column] != value]
                elif operator == "!=":
                    result = result[result[column] == value]
                elif operator == ">":
                    result = result[result[column] <= pd.to_numeric(value)]
                elif operator == "<":
                    result = result[result[column] >= pd.to_numeric(value)]
                elif operator == ">=":
                    result = result[result[column] < pd.to_numeric(value)]
                elif operator == "<=":
                    result = result[result[column] > pd.to_numeric(value)]
            except Exception as e:
                return dataframe, f"Comparison failed: {e}"
            return result.reset_index(drop=True), None

        elif command.command_type == "fill_missing":
            column = command.params["column"]
            strategy = command.params["strategy"]
            if column not in dataframe.columns:
                return dataframe, f"Column '{column}' not found."
            result = dataframe.copy()
            if strategy == "median":
                result[column] = result[column].fillna(result[column].median())
            elif strategy == "mean":
                result[column] = result[column].fillna(result[column].mean())
            elif strategy == "mode":
                mode_val = result[column].mode()
                fill_val = mode_val.iloc[0] if not mode_val.empty else "Unknown"
                result[column] = result[column].fillna(fill_val)
            elif strategy == "zero":
                result[column] = result[column].fillna(0)
            elif strategy == "forward":
                result[column] = result[column].fillna(method="ffill")
            elif strategy == "backward":
                result[column] = result[column].fillna(method="bfill")
            return result, None

        return dataframe, "Command type not implemented."

    except Exception as e:
        return dataframe, f"Error applying command: {str(e)}"
