from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class ModeState:
    mode: Literal["auto", "manual"]
    pandas_enabled: bool
    numpy_enabled: bool
    sql_enabled: bool


def get_default_mode() -> ModeState:
    """Auto mode with all engines enabled by default."""
    return ModeState(mode="auto", pandas_enabled=True, numpy_enabled=True, sql_enabled=True)


def create_manual_mode(pandas: bool = True, numpy: bool = True, sql: bool = True) -> ModeState:
    """Manual mode with selective engine control."""
    return ModeState(mode="manual", pandas_enabled=pandas, numpy_enabled=numpy, sql_enabled=sql)


def format_mode_status(state: ModeState) -> dict[str, bool]:
    """Return active engine status for display."""
    return {
        "Pandas (cleaning/profiling)": state.pandas_enabled,
        "NumPy (correlation/analysis)": state.numpy_enabled,
        "SQL (audit history)": state.sql_enabled,
    }
