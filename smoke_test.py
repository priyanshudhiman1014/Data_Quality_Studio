#!/usr/bin/env python
"""Comprehensive smoke test for all new capabilities."""

import pandas as pd
from data_quality.mode_manager import get_default_mode, create_manual_mode
from data_quality.chat_commands import parse_chat_command, apply_chat_command
from data_quality.advanced_analysis import compute_correlations, data_quality_score, segment_by_column
from data_quality.sql_safe_queries import validate_sql_query, execute_safe_sql
from data_quality.processing import profile_dataframe

# Test 1: Mode control
print("✓ Test 1: Mode control")
auto_mode = get_default_mode()
assert auto_mode.pandas_enabled and auto_mode.numpy_enabled and auto_mode.sql_enabled
manual_mode = create_manual_mode(pandas=True, numpy=False, sql=True)
assert not manual_mode.numpy_enabled
print("  Auto mode all engines enabled, manual mode selective control works")

# Test 2: Chat commands
print("✓ Test 2: Chat commands (natural language)")
df = pd.DataFrame({'name': ['Alice', 'Bob'], 'score': [85, 92], 'temp': [1, 2]})
cmd1 = parse_chat_command("rename score to rating")
assert cmd1.valid and cmd1.command_type == "rename"
modified1, err1 = apply_chat_command(df, cmd1)
assert err1 is None and "rating" in modified1.columns
print("  Rename command works")

cmd2 = parse_chat_command("drop temp")
assert cmd2.valid and cmd2.command_type == "drop"
modified2, err2 = apply_chat_command(modified1, cmd2)
assert err2 is None and "temp" not in modified2.columns
print("  Drop command works")

# Test 3: Advanced analysis
print("✓ Test 3: Advanced analysis")
numeric_df = pd.DataFrame({'a': [1, 2, 3], 'b': [2, 4, 6], 'c': [5, 5, 5]})
corr = compute_correlations(numeric_df)
assert not corr.empty and 'a' in corr.columns
print("  Correlation matrix computed")

profile = profile_dataframe(numeric_df)
score = data_quality_score(numeric_df, profile)
assert 0 <= score <= 1
print(f"  Quality score computed: {score:.2f}")

segments = segment_by_column(numeric_df, 'c')
assert len(segments) > 0
print("  Data segmentation works")

# Test 4: SQL safety
print("✓ Test 4: SQL query safety")
valid_select, err_select = validate_sql_query("SELECT * FROM data LIMIT 10")
assert valid_select and err_select is None
print("  SELECT allowed")

valid_insert, err_insert = validate_sql_query("INSERT INTO data VALUES (1, 2, 3)")
assert not valid_insert
print("  INSERT blocked")

valid_update, err_update = validate_sql_query("UPDATE data SET x = 1")
assert not valid_update
print("  UPDATE blocked")

# Test 5: Safe SQL execution
print("✓ Test 5: Safe SQL execution")
test_df = pd.DataFrame({'id': [1, 2, 3], 'value': [10, 20, 30]})
result, err = execute_safe_sql(test_df, "SELECT * FROM data WHERE value > 15")
assert err is None and len(result) == 2
print("  Safe SELECT executed locally")

print("\n✓✓✓ All smoke tests passed - full capabilities unlocked and working ✓✓✓")
