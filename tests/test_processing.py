import pandas as pd

from data_quality.processing import clean_dataframe, improve_dataframe, prepare_csv_export, profile_dataframe, run_hypothesis_test


def test_cleaning_removes_duplicates_trims_and_fills_missing():
    frame = pd.DataFrame({" name ": [" Alice ", " Alice ", "Bob"], "score": [10, 10, None]})
    result = clean_dataframe(frame)
    assert len(result.dataframe) == 2
    assert result.dataframe["name"].tolist() == ["Alice", "Bob"]
    assert result.dataframe["score"].isna().sum() == 0
    assert not result.errors


def test_profile_counts_quality_issues():
    frame = pd.DataFrame({"value": [1, 2, 3, 4, 5, 100], "label": ["a", "a", "b", "c", "d", "e"]})
    report = profile_dataframe(frame)
    assert report["rows"] == 6
    assert report["missing_cells"] == 0
    assert report["duplicate_rows"] == 0
    assert report["outliers"]["value"] >= 1


def test_one_sample_t_test_returns_decision():
    frame = pd.DataFrame({"value": [9, 10, 11, 10, 10]})
    result = run_hypothesis_test(frame, "One-sample t-test", "value", reference_value=0)
    assert 0 <= result["p_value"] <= 1
    assert result["decision"] == "Reject H0"


def test_csv_export_neutralizes_formula_like_text():
    frame = pd.DataFrame({"note": ["=SUM(A1:A2)", "normal"]})
    exported = prepare_csv_export(frame)
    assert exported["note"].tolist() == ["'=SUM(A1:A2)", "normal"]


def test_improvement_tools_standardize_text_parse_dates_and_remove_empty_columns():
    frame = pd.DataFrame(
        {
            "Customer Name": ["alice smith", "bob jones"],
            "Order Date": ["2026-01-02", "2026-01-03"],
            "Empty": [None, None],
        }
    )
    result = improve_dataframe(frame, standardize_columns=True, text_case="Title Case", parse_dates=True, remove_empty=True)
    assert list(result.dataframe.columns) == ["customer_name", "order_date"]
    assert str(result.dataframe["order_date"].dtype).startswith("datetime64")
    assert result.dataframe["customer_name"].tolist() == ["Alice Smith", "Bob Jones"]
