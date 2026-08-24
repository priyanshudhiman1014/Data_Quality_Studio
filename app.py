from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from data_quality.advanced_analysis import (
    compute_correlations,
    data_quality_score,
    execute_validation,
    find_strong_correlations,
    generate_quality_summary,
    sample_data,
    segment_by_column,
)
from data_quality.ai_insights import request_ai_interpretation
from data_quality.chat_commands import apply_chat_command, parse_chat_command
from data_quality.export_utils import generate_combined_export, generate_html_report, generate_separate_exports, prepare_csv_export
from data_quality.mode_manager import create_manual_mode, format_mode_status, get_default_mode
from data_quality.processing import clean_dataframe, improve_dataframe, profile_dataframe, run_hypothesis_test
from data_quality.sql_safe_queries import execute_safe_sql, query_to_dataframe, suggest_queries
from data_quality.storage import AuditStore


st.set_page_config(page_title="Data Quality Studio", page_icon="DQ", layout="wide")

st.markdown("""
<style>
:root { --ink: #17221d; --muted: #68736c; --paper: #fbfaf5; --mint: #c9f2df; --orange: #ee8d57; --line: #dfe8df; }
.stApp { background: var(--paper); }
.block-container { max-width: 1400px; padding-top: 1.25rem; padding-bottom: 3rem; }
.hero { background: linear-gradient(120deg, #17221d 0%, #294438 62%, #496c58 100%); color: white; padding: 2.35rem 2.5rem; border-radius: 18px; margin-bottom: 1.2rem; box-shadow: 0 12px 30px rgba(23, 34, 29, .12); }
.hero h1 { font-family: Georgia, serif; font-size: clamp(2rem, 4vw, 3.2rem); line-height: 1.05; margin: 0 0 .7rem; letter-spacing: 0; }
.hero p { color: #d9ebe0; max-width: 720px; font-size: 1.05rem; margin-bottom: 0; }
.workflow { display: flex; gap: .65rem; flex-wrap: wrap; margin: 0 0 1.35rem; }
.workflow span { background: #eef4ee; border: 1px solid var(--line); color: #3f5749; padding: .45rem .75rem; border-radius: 999px; font-size: .84rem; font-weight: 600; }
.workflow span strong { color: var(--orange); margin-right: .25rem; }
.section-kicker { color: #53715f; text-transform: uppercase; letter-spacing: .08em; font-size: .72rem; font-weight: 800; margin: .35rem 0 .15rem; }
.metric { background: #f1f6f2; border: 1px solid var(--line); border-top: 3px solid var(--orange); padding: .8rem 1rem; border-radius: 10px; }
[data-testid="stMetricValue"] { color: var(--ink); }
[data-testid="stMetricLabel"] { color: var(--muted); }
[data-testid="stFileUploader"] { background: #fff; border: 1px dashed #9ab8a4; border-radius: 12px; padding: .35rem; }
[data-testid="stTabs"] button { color: #52655a; font-weight: 650; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #c76432; border-bottom-color: var(--orange); }
[data-testid="stSidebar"] { background: #f0f5ef; border-right: 1px solid var(--line); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: var(--ink); font-family: Georgia, serif; }
.privacy-note { background: #e9f5ed; border-left: 4px solid #6ba37b; color: #355341; padding: .7rem .85rem; border-radius: 6px; font-size: .86rem; }
.quality-badge { display: inline-block; padding: .25rem .6rem; border-radius: 999px; font-weight: 800; background: #dff2e5; color: #2b7545; }
@media (max-width: 700px) { .hero { padding: 1.6rem; } .hero h1 { font-size: 2rem; } .block-container { padding-left: 1rem; padding-right: 1rem; } }
</style>
<div class="hero"><h1>Data Quality Studio</h1><p>Turn raw CSV files into trusted, documented datasets while everything stays on this Windows machine.</p></div>
<div class="workflow"><span><strong>01</strong> Upload</span><span><strong>02</strong> Inspect</span><span><strong>03</strong> Improve</span><span><strong>04</strong> Validate</span><span><strong>05</strong> Export</span></div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-kicker">Start here</div>', unsafe_allow_html=True)
st.subheader("Bring in your data")
st.caption("Choose one or more CSV files. They are processed in memory and are never staged on disk.")
uploaded_files = st.file_uploader("CSV files", type=["csv"], accept_multiple_files=True, label_visibility="collapsed")
if not uploaded_files:
    st.info("Your workspace is ready. Upload one or more CSV files to begin profiling and cleaning.")
    st.stop()

total_upload_size = sum(file.size for file in uploaded_files)
if total_upload_size > 500 * 1024 * 1024:
    st.error("The selected files exceed the combined 500 MB privacy and resource limit.")
    st.stop()

frames = []
read_errors = []
for uploaded_file in uploaded_files:
    try:
        file_frame = pd.read_csv(uploaded_file, encoding_errors="replace")
        file_frame.insert(0, "source_file", Path(uploaded_file.name).name)
        frames.append(file_frame)
    except Exception as error:
        read_errors.append(f"{uploaded_file.name}: {error}")
if read_errors:
    for read_error in read_errors:
        st.error(f"Could not read CSV: {read_error}")
if not frames:
    st.stop()
original = pd.concat(frames, ignore_index=True, sort=False)
dataset_name = ", ".join(Path(file.name).name for file in uploaded_files[:3])
if len(uploaded_files) > 3:
    dataset_name += f" (+{len(uploaded_files) - 3} more)"
st.markdown(f'<div class="privacy-note">Loaded <strong>{len(uploaded_files)} file(s)</strong> · {total_upload_size / (1024 * 1024):.1f} MB total · {len(original):,} combined rows · local processing only</div>', unsafe_allow_html=True)

original_profile = profile_dataframe(original)

with st.sidebar:
    st.header("Your workspace")
    st.caption("Choose how much control you want over the processing engines.")
    mode_choice = st.radio("Processing mode", ["Auto (all engines)", "Manual"])
    if mode_choice == "Auto (all engines)":
        mode_state = get_default_mode()
    else:
        st.write("**Engine control:**")
        pandas_on = st.checkbox("Pandas", value=True, help="Data cleaning and profiling")
        numpy_on = st.checkbox("NumPy", value=True, help="Correlation and numeric analysis")
        sql_on = st.checkbox("SQL", value=True, help="Audit history and safe queries")
        mode_state = create_manual_mode(pandas=pandas_on, numpy=numpy_on, sql=sql_on)

    st.divider()
    st.subheader("Engine status")
    for engine, active in format_mode_status(mode_state).items():
        st.success(f"✓ {engine}" if active else f"✗ {engine}")

    st.divider()
    st.header("Improve the data")
    auto_clean = st.button("Auto-clean now", type="primary", use_container_width=True, help="Apply the recommended cleaning defaults.")
    missing_strategy = st.selectbox("How to handle missing values", ["median", "mean", "mode", "zero", "drop_rows"])
    remove_duplicates = st.checkbox("Remove duplicate rows", value=True)
    trim_text = st.checkbox("Trim extra text spaces", value=True)
    with st.expander("More improvement tools"):
        standardize_columns = st.checkbox("Standardize column names", value=False, help="Convert headers to lowercase snake_case, such as order_date.")
        text_case = st.selectbox("Text style", ["Keep original", "lowercase", "Title Case"], help="Apply a consistent style to text values.")
        parse_dates = st.checkbox("Detect date-like columns", value=False, help="Convert columns that are mostly recognizable dates into date values.")
        remove_empty = st.checkbox("Remove fully empty rows and columns", value=True)
    run_cleaning = st.button("Apply selected cleaning", type="secondary", use_container_width=True)

    st.divider()
    st.header("Optional AI insights")
    enable_ai = st.toggle("Enable external AI", value=False, help="Allow the AI interpretation tab to send aggregate statistics to your configured provider.")
    if enable_ai:
        ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
        default_ai_base_url = (
            os.getenv("OMNIROUTE_BASE_URL", "")
            if ai_provider == "omniroute"
            else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        ai_api_key = st.text_input("API key", type="password", value="", help="Used for this session only; it is not saved to disk.")
        ai_base_url = st.text_input(
            "Base URL",
            value=default_ai_base_url,
            help="OpenAI-compatible API endpoint, including /v1 when required.",
        )
        st.warning("Aggregate statistics may be sent to the configured AI provider.")
    else:
        ai_api_key = ""
        ai_base_url = ""
        st.caption("AI is off. No external AI request can be made.")

cleaning_input = original
pre_clean_changes: list[str] = []
if remove_empty:
    empty_columns = cleaning_input.columns[cleaning_input.isna().all()].tolist()
    if empty_columns:
        cleaning_input = cleaning_input.drop(columns=empty_columns)
        pre_clean_changes.append(f"Removed {len(empty_columns)} completely empty column(s)")
    before_empty_rows = len(cleaning_input)
    cleaning_input = cleaning_input.dropna(how="all").reset_index(drop=True)
    if before_empty_rows != len(cleaning_input):
        pre_clean_changes.append(f"Removed {before_empty_rows - len(cleaning_input)} completely empty row(s)")

if auto_clean:
    result = clean_dataframe(cleaning_input, "median", True, True)
    cleaned = result.dataframe
    st.success("✓ Auto clean completed: duplicates removed, text trimmed, missing values filled.")
else:
    result = clean_dataframe(cleaning_input, missing_strategy, remove_duplicates, trim_text)
    cleaned = result.dataframe
result.changes = pre_clean_changes + result.changes

improvement_result = improve_dataframe(
    cleaned,
    standardize_columns=standardize_columns,
    text_case=text_case,
    parse_dates=parse_dates,
    remove_empty=remove_empty,
)
cleaned = improvement_result.dataframe
result.changes.extend(improvement_result.changes)
result.errors.extend(improvement_result.errors)

cleaned_profile = profile_dataframe(cleaned)

if run_cleaning or auto_clean or "processed" not in st.session_state:
    st.session_state["processed"] = True
    if mode_state.sql_enabled:
        try:
            AuditStore(Path(__file__).with_name("data_quality.db")).save_run(dataset_name, original_profile, cleaned_profile, result.changes)
        except Exception as error:
            st.warning(f"The dataset was processed, but audit history could not be saved: {error}")

st.markdown('<div class="section-kicker">Quality snapshot</div>', unsafe_allow_html=True)
st.subheader("How healthy is the cleaned dataset?")
quality_summary = generate_quality_summary(cleaned, cleaned_profile)
quality_grade_class = {
    "A": "quality-a",
    "B": "quality-b",
    "C": "quality-c",
    "D": "quality-d",
}.get(quality_summary["quality_grade"], "")

metrics = st.columns(6)
metrics[0].metric("Rows", f"{cleaned_profile['rows']:,}")
metrics[1].metric("Columns", f"{cleaned_profile['columns']}")
metrics[2].metric("Missing cells", f"{cleaned_profile['missing_cells']}")
metrics[3].metric("Duplicates", f"{cleaned_profile['duplicate_rows']}")
metrics[4].metric("Outliers", f"{int(cleaned_profile['outliers'].sum())}")
metrics[5].metric("Quality Grade", f"**{quality_summary['quality_grade']}** ({quality_summary['quality_score']:.1%})")
st.markdown(f'<span class="quality-badge">Grade {quality_summary["quality_grade"]} · {quality_summary["quality_score"]:.1%} overall quality</span>', unsafe_allow_html=True)

st.divider()
st.markdown('<div class="section-kicker">Review and export</div>', unsafe_allow_html=True)
st.subheader("See what changed, then take the result with you")
left, right = st.columns([1.5, 1])
with left:
    st.write("**Cleaned dataset preview**")
    st.dataframe(cleaned.head(100), use_container_width=True, height=330)

with right:
    st.write("**Export your work**")
    safe_export = prepare_csv_export(cleaned)
    csv_bytes, combined_name = generate_combined_export(safe_export, Path(uploaded_files[0].name).stem)
    st.download_button("📥 Combined CSV", csv_bytes, file_name=combined_name, mime="text/csv", use_container_width=True)

    separate_exports = generate_separate_exports(original, safe_export)
    if len(separate_exports) > 1:
        for csv_data, filename in separate_exports:
            st.download_button(f"📥 {filename}", csv_data, file_name=filename, mime="text/csv", use_container_width=True)

    html_report = generate_html_report(cleaned_profile, result.changes)
    st.download_button("📊 Quality Report (HTML)", html_report.encode("utf-8"), file_name=f"quality_report_{dataset_name}.html", mime="text/html", use_container_width=True)

st.divider()
st.markdown('<div class="section-kicker">Workbenches</div>', unsafe_allow_html=True)
st.subheader("Explore, test, and document")
main_tabs = st.tabs(["Run Summary", "Overview", "Statistical Tests", "Change Data", "Explore Data", "Safe SQL", "AI Insights", "History"])

with main_tabs[0]:
    st.caption("A before-and-after record of what Data Quality Studio changed in this run.")
    before_rows = original_profile["rows"]
    after_rows = cleaned_profile["rows"]
    before_columns = original_profile["columns"]
    after_columns = cleaned_profile["columns"]
    before_missing = original_profile["missing_cells"]
    after_missing = cleaned_profile["missing_cells"]
    before_duplicates = original_profile["duplicate_rows"]
    after_duplicates = cleaned_profile["duplicate_rows"]
    before_outliers = int(original_profile["outliers"].sum())
    after_outliers = int(cleaned_profile["outliers"].sum())

    st.markdown("### Impact at a glance")
    impact = st.columns(5)
    impact[0].metric("Rows", f"{after_rows:,}", delta=f"{after_rows - before_rows:+,}")
    impact[1].metric("Columns", f"{after_columns}", delta=f"{after_columns - before_columns:+}")
    impact[2].metric("Missing cells", f"{after_missing:,}", delta=f"{after_missing - before_missing:+,}", delta_color="inverse")
    impact[3].metric("Duplicates", f"{after_duplicates:,}", delta=f"{after_duplicates - before_duplicates:+,}", delta_color="inverse")
    impact[4].metric("Outliers", f"{after_outliers:,}", delta=f"{after_outliers - before_outliers:+,}", delta_color="inverse")

    st.markdown("### Before and after")
    comparison = pd.DataFrame(
        [
            ["Rows", before_rows, after_rows, after_rows - before_rows],
            ["Columns", before_columns, after_columns, after_columns - before_columns],
            ["Missing cells", before_missing, after_missing, after_missing - before_missing],
            ["Duplicate rows", before_duplicates, after_duplicates, after_duplicates - before_duplicates],
            ["Outlier values", before_outliers, after_outliers, after_outliers - before_outliers],
        ],
        columns=["Measure", "Before", "After", "Change"],
    )
    st.dataframe(comparison, hide_index=True, use_container_width=True)

    st.markdown("### Column-level impact")
    before_missing_by_column = original_profile["missing_by_column"]
    after_missing_by_column = cleaned_profile["missing_by_column"]
    all_profile_columns = list(dict.fromkeys([*original.columns.tolist(), *cleaned.columns.tolist()]))
    column_impact = []
    for column in all_profile_columns:
        before_exists = column in original.columns
        after_exists = column in cleaned.columns
        column_impact.append(
            {
                "Column": column,
                "Status": "Unchanged" if before_exists and after_exists else "Added" if after_exists else "Removed",
                "Missing before": int(before_missing_by_column.get(column, 0)),
                "Missing after": int(after_missing_by_column.get(column, 0)),
                "Type before": str(original[column].dtype) if before_exists else "—",
                "Type after": str(cleaned[column].dtype) if after_exists else "—",
            }
        )
    st.dataframe(pd.DataFrame(column_impact), hide_index=True, use_container_width=True)

    summary_left, summary_right = st.columns([1.15, 1])
    with summary_left:
        st.markdown("### What changed")
        if result.changes:
            for change in result.changes:
                st.success(change, icon="✅")
        else:
            st.info("No transformations were needed for this run.")
        if result.errors:
            st.markdown("### Items needing attention")
            for error in result.errors:
                st.warning(error, icon="⚠️")
    with summary_right:
        st.markdown("### Quality movement")
        original_quality = generate_quality_summary(original, original_profile)
        quality_delta = quality_summary["quality_score"] - original_quality["quality_score"]
        quality_columns = st.columns(2)
        quality_columns[0].metric("Before", f"{original_quality['quality_score']:.1%}", f"Grade {original_quality['quality_grade']}")
        quality_columns[1].metric("After", f"{quality_summary['quality_score']:.1%}", f"{quality_delta:+.1%}")
        st.progress(quality_summary["quality_score"], text=f"Final quality: Grade {quality_summary['quality_grade']}")
        st.caption("The score combines completeness and uniqueness. Outliers are reported for review and are not automatically removed.")

        st.markdown("### Privacy record")
        st.markdown('<div class="privacy-note">The original CSV was kept in memory for comparison. Only aggregate run metadata is eligible for local audit history; raw cell values are not stored.</div>', unsafe_allow_html=True)

with main_tabs[1]:
    st.write("**Numeric summary**")
    if cleaned_profile["numeric_summary"].empty:
        st.warning("No numeric columns detected.")
    else:
        st.dataframe(cleaned_profile["numeric_summary"], use_container_width=True)

    st.write("**Missing values by column**")
    missing = cleaned_profile["missing_by_column"]
    st.dataframe(missing.rename("missing_cells").to_frame(), use_container_width=True)

    st.write("**Potential outliers (IQR method)**")
    st.dataframe(cleaned_profile["outliers"].rename("outlier_count").to_frame(), use_container_width=True)

with main_tabs[2]:
    st.caption("Use a statistical test to compare patterns in the cleaned data. Results are evidence, not proof of causation.")
    numeric_columns = cleaned.select_dtypes(include="number").columns.tolist()
    all_columns = cleaned.columns.tolist()
    test_name = st.selectbox("Test", ["One-sample t-test", "Independent two-group t-test", "Chi-square independence test", "Shapiro-Wilk normality test"])
    selected_column = st.selectbox("Primary column", all_columns)
    reference_value = 0.0
    group_column = None
    group_a = None
    group_b = None
    second_column = None
    if test_name in {"One-sample t-test", "Independent two-group t-test", "Shapiro-Wilk normality test"}:
        selected_column = st.selectbox("Numeric column", numeric_columns) if numeric_columns else selected_column
    if test_name == "One-sample t-test":
        reference_value = st.number_input("Reference mean", value=0.0)
    elif test_name == "Independent two-group t-test":
        group_options = [column for column in all_columns if column != selected_column]
        group_column = st.selectbox("Grouping column", group_options) if group_options else None
        groups = cleaned[group_column].dropna().astype(str).unique().tolist() if group_column else []
        if len(groups) >= 2:
            group_a, group_b = st.selectbox("Group A", groups), st.selectbox("Group B", groups, index=1)
    elif test_name == "Chi-square independence test":
        second_options = [column for column in all_columns if column != selected_column]
        second_column = st.selectbox("Second categorical column", second_options) if second_options else None
    if st.button("Run test", type="primary"):
        try:
            test_result = run_hypothesis_test(cleaned, test_name, selected_column, reference_value, group_column, group_a, group_b, second_column)
            a, b, c = st.columns(3)
            a.metric("Statistic", f"{test_result['statistic']:.4f}")
            b.metric("p-value", f"{test_result['p_value']:.4g}")
            c.metric("Decision", test_result["decision"])
            st.write(test_result["null_hypothesis"])
            st.caption("Decision threshold: alpha = 0.05.")
        except Exception as error:
            st.error(f"Test could not be run: {error}")

with main_tabs[3]:
    st.caption("Describe one safe transformation at a time. The original upload remains unchanged.")
    st.info("Examples: `rename score to rating`, `drop temp_col`, `keep only id, name, value`, `fill missing in age with median`, `remove rows where status == archived`")

    user_command = st.text_input("Enter a data change command:", placeholder="e.g., rename column_name to new_name")
    if user_command:
        parsed = parse_chat_command(user_command)
        if not parsed.valid:
            st.error(f"Error: {parsed.error}")
        else:
            modified, error = apply_chat_command(cleaned, parsed)
            if error:
                st.error(f"Failed to apply: {error}")
            else:
                st.success(f"✓ Command applied: {user_command}")
                st.write("**Preview of modified data:**")
                st.dataframe(modified.head(20), use_container_width=True)

                modified_safe = prepare_csv_export(modified)
                modified_csv = modified_safe.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download modified data", modified_csv, file_name=f"chat_modified_{dataset_name}.csv", mime="text/csv", use_container_width=True)

with main_tabs[4]:
    st.caption("Find relationships, inspect groups, sample rows, and check validation rules.")
    if mode_state.numpy_enabled:
        st.write("**NumPy-powered correlation analysis:**")
        corr_matrix = compute_correlations(cleaned)
        if corr_matrix.empty:
            st.warning("Insufficient numeric columns for correlation analysis.")
        else:
            st.dataframe(corr_matrix, use_container_width=True)
            strong_corrs = find_strong_correlations(corr_matrix)
            if strong_corrs:
                st.write("**Strong correlations (|r| ≥ 0.7):**")
                for col1, col2, corr_val in strong_corrs:
                    st.write(f"- `{col1}` ↔ `{col2}`: {corr_val:.3f}")
    else:
        st.info("NumPy is disabled. Enable it in the sidebar to use correlation analysis.")

    st.divider()
    st.write("**Data segmentation:**")
    segment_col = st.selectbox("Segment by column:", cleaned.columns)
    if segment_col:
        segments = segment_by_column(cleaned, segment_col)
        for segment_name, segment_data in segments.items():
            st.write(f"**{segment_name}** - {len(segment_data):,} rows")

    st.divider()
    st.write("**Data sampling:**")
    sample_type = st.radio("Sample type:", ["Absolute (N rows)", "Fraction (0-100%)"])
    if sample_type == "Absolute (N rows)":
        sample_size = st.number_input("Sample size:", min_value=1, value=100)
        sample_result = sample_data(cleaned, sample_size=sample_size)
    else:
        sample_frac = st.slider("Fraction:", 0.0, 1.0, 0.1)
        sample_result = sample_data(cleaned, fraction=sample_frac)
    st.write(f"**Sample:** {len(sample_result):,} rows")

    st.divider()
    st.write("**Validation rules:**")
    rule_name = st.text_input("Rule name:", placeholder="e.g., 'positive_score'")
    rule_column = st.selectbox("Column:", cleaned.columns, key="validation_col")
    rule_type = st.selectbox("Type:", ["not_null", "range", "pattern", "unique", "enum", "custom_numeric"])

    if rule_type == "range" and rule_name:
        min_val = st.number_input("Min value:", value=0.0)
        max_val = st.number_input("Max value:", value=100.0)
        rule = {"name": rule_name, "column": rule_column, "type": "range", "params": {"min": min_val, "max": max_val}}
        passed, violations = execute_validation(cleaned, rule)
        st.metric(f"Rule: {rule_name}", "✓ PASS" if passed else f"✗ FAIL ({violations} violations)")

with main_tabs[5]:
    if mode_state.sql_enabled:
        st.caption("Run read-only SELECT statements against an in-memory copy of the cleaned dataset.")
        st.info("Only SELECT statements allowed. CSV data is never modified by SQL.")

        st.write("**Quick suggestions:**")
        for i, query in enumerate(suggest_queries(cleaned)):
            if st.button(query, key=f"suggest_{i}"):
                st.session_state["sql_query"] = query

        user_query = st.text_area("Enter SQL query:", value=st.session_state.get("sql_query", ""), height=100)
        if st.button("Execute query"):
            result, error = execute_safe_sql(cleaned, user_query)
            if error:
                st.error(f"Query failed: {error}")
            else:
                result_info = query_to_dataframe(result)
                st.write(f"**Result:** {result_info['rows']} rows × {result_info['columns']} columns")
                st.dataframe(result_info["data"], use_container_width=True)

                if result is not None:
                    result_csv = result.to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Download query result", result_csv, file_name=f"sql_result_{dataset_name}.csv", mime="text/csv", use_container_width=True)
    else:
        st.info("SQL is disabled. Enable it in the sidebar to use safe SQL queries.")

with main_tabs[6]:
    st.caption("Generate an analyst-style interpretation from aggregate quality statistics only.")
    if not enable_ai:
        st.info("Enable external AI from the sidebar before generating an interpretation.")
    else:
        st.warning("Privacy: this sends only row counts, missing-value counts, outlier counts, and numeric summaries. CSV rows are never sent.")
    if enable_ai and st.button("Generate AI interpretation", type="primary"):
        try:
            with st.spinner("Generating interpretation..."):
                interpretation = request_ai_interpretation(cleaned_profile, api_key=ai_api_key, base_url=ai_base_url)
            st.markdown(interpretation)
        except Exception as error:
            st.error(str(error))
    st.caption("Configure environment variables OPENAI_API_KEY or OMNIROUTE_API_KEY before starting the app.")

with main_tabs[7]:
    st.caption("Review metadata about previous processing runs. Raw CSV values are never stored here.")
    if mode_state.sql_enabled:
        try:
            runs = AuditStore(Path(__file__).with_name("data_quality.db")).recent_runs()
            if runs:
                st.dataframe(pd.DataFrame(runs, columns=["dataset", "processed_at", "original_rows", "cleaned_rows", "changes"]), use_container_width=True)
            else:
                st.info("No audit runs yet.")
        except Exception as error:
            st.error(f"Could not load audit history: {error}")
    else:
        st.info("SQL is disabled. Enable it in the sidebar to view audit history.")
