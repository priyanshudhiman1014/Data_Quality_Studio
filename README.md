# Data Quality Studio – Full Capabilities Edition (AI-Assisted)

A comprehensive local Streamlit application for CSV cleaning, profiling, quality assessment, advanced analytics (correlation, segmentation, sampling), safe SQL querying, natural-language data editing, and AI-assisted insights—**all with strict local-only privacy and no data exposure**.

## Run

### Windows one-click launch

Double-click [`run_windows.bat`](run_windows.bat). The launcher creates a local virtual environment, installs the pinned application requirements, and opens the dashboard in your browser at `http://127.0.0.1:8501`.

```powershell
cd "D:\VS Code\data_quality_app"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Upload one or more CSV files and unlock full data quality capabilities. Each row keeps its originating filename in `source_file`. Audit metrics are stored in `data_quality.db` using SQLite (metadata only).

CSV uploads up to 500 MB are supported. Multi-file uploads are supported with automatic provenance tracking. Large files require sufficient available memory because Pandas processes the dataset locally in memory.

See [`PRIVACY.md`](PRIVACY.md) for the local-only processing and security behavior.

---

## Core Features

### Processing Modes

- **Auto Mode** (default): All engines (Pandas, NumPy, SQL) enabled for full processing power.
- **Manual Mode**: Selectively enable/disable Pandas (cleaning/profiling), NumPy (correlation/analysis), and SQL (audit history).

### Data Cleaning & Profiling

- **Auto-clean button** (1-click): Automatic cleaning with deduplication, whitespace trimming, and median-based missing value filling.
- **Configurable cleaning rules**: Missing value strategies (median, mean, mode, zero, drop rows), duplicate removal, text trimming.
- **Improvement tools**: Standardize headers to lowercase snake_case, apply lowercase or Title Case text, detect date-like columns, and remove fully empty rows or columns.
- **Run Summary screen**: Before/after row, column, missing-value, duplicate, outlier, quality-grade, and column-type comparisons, plus a complete transformation log.
- **Comprehensive profiling**: Row/column counts, missing-value detection, outlier identification (IQR method), numeric summaries.
- **Quality scoring**: 0.0–1.0 scale with letter grades (A/B/C/D) combining completeness (60%) and uniqueness (40%).
- **Error-free operation**: All transformations logged and validated; original data preserved in memory.

### Data Transformation with Chat-like Commands

The **Chat Changes** tab offers natural-language-like data editing *without arbitrary code execution*:

- `rename <old_col> to <new_col>` – Rename columns
- `drop <col>` – Remove columns
- `keep only <col1>, <col2>, ...` – Filter to specific columns
- `duplicate <source_col> as <new_col>` – Create column copies
- `remove rows where <col> <op> <value>` – Filter rows (operators: ==, !=, >, <, >=, <=)
- `fill missing in <col> with <strategy>` – Handle missing values (median, mean, mode, zero, forward, backward)

All commands are regex-parsed (no `eval()` or arbitrary Python). Errors are caught and reported clearly.

### Advanced Analysis (NumPy-powered, mode-gated)

- **Correlation matrices**: Pearson correlation for numeric columns.
- **Strong correlations**: Automatically detect pairs with |r| ≥ 0.7.
- **Data segmentation**: Group data by unique values in any column.
- **Statistical sampling**: Absolute size or fractional sampling with fixed seed (42).
- **Validation rules**: Define and execute rules for not_null, range, pattern, unique, enum, custom numeric constraints.

### Hypothesis Testing

- One-sample t-test against a reference mean
- Independent two-group t-test
- Chi-square test of independence for two categorical columns
- Shapiro-Wilk normality test (all with alpha=0.05)

Results display statistic, p-value, and decision (Reject / Fail to reject null hypothesis).

### Safe SQL Queries (mode-gated)

The **SQL Queries** tab executes read-only SELECT queries locally on in-memory data:

- **Keyword-based validation**: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, EXEC, PRAGMA, and multi-statement queries are blocked at parse time.
- **In-memory execution**: SQLite runs queries locally; no persistence, no data written to disk.
- **Quick suggestions**: Auto-generated SELECT examples based on your schema.
- **Result download**: Export query results as CSV.

### Export Flexibility

- **Combined dataset CSV**: Merged cleaned data with source_file column tracking provenance.
- **Separate exports**: Individual cleaned CSVs per source file (if multi-file upload).
- **Quality report (HTML)**: Standalone report with metrics, cleaning log, numeric summaries, and missing-value breakdown.
- **Formula-injection protection**: Dangerous cell prefixes (=, +, -, @) automatically escaped with apostrophe prefix to prevent spreadsheet formula injection.

### AI-assisted Insights

The **AI Insights** tab generates analyst-style interpretations from aggregate statistics (opt-in, aggregate-only transmission).

### Audit History (mode-gated, SQL)

SQLite audit storage records metadata-only: dataset names, timestamps, row/column counts, cleaning changes (JSON), quality metrics (JSON). **Raw CSV data is never stored; only statistics.**

---

## AI-assisted Interpretation (Optional)

The **AI Insights** tab is **opt-in** and **off by default**. External calls require:

1. Toggle "Enable external AI" in the sidebar
2. Environment variables set before starting the app
3. Valid provider API key (Omniroute or OpenAI)

### Omniroute Setup (Free Tier)

For Omniroute (no billing charges, free-tier API):

```powershell
$env:AI_PROVIDER = "omniroute"
$env:AI_ALLOW_EXTERNAL = "true"  # Explicit consent flag
$env:OMNIROUTE_API_KEY = "your-api-key-here"
$env:OMNIROUTE_BASE_URL = "https://your-omniroute-endpoint/v1"
$env:OMNIROUTE_MODEL = "your-free-model-id"
streamlit run app.py
```

### OpenAI Setup

For OpenAI:

```powershell
$env:AI_PROVIDER = "openai"
$env:AI_ALLOW_EXTERNAL = "true"
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"  # (default)
$env:OPENAI_MODEL = "gpt-4o-mini"  # (default)
streamlit run app.py
```

**Data Privacy Guarantee**: Only aggregate statistics are transmitted—row/column counts, missing-value counts, outlier counts, and numeric summaries (mean, std, min, max, quartiles). **Raw CSV rows and text values are never sent.** The application does not generate API keys; keys belong to the provider account and may incur charges per provider policy; the app cannot guarantee free usage.

---

## Technology Stack

- **Streamlit ≥1.36**: Interactive web dashboard with local-only binding (127.0.0.1), XSRF protection, telemetry disabled
- **Pandas ≥2.2**: Core data manipulation, cleaning, and profiling
- **NumPy ≥1.26**: Numeric analysis (correlation, segmentation, sampling)
- **SciPy ≥1.13**: Hypothesis testing (t-tests, chi-square, Shapiro-Wilk)
- **SQLite3**: Metadata-only audit history (Python standard library)
- **Python 3.10+**: Runtime
- **Windows Batch launcher** (`run_windows.bat`): Virtual environment setup, dependency installation, auto-start

---

## Security & Privacy Principles

✓ **Local-only processing**: All computation happens on your machine (127.0.0.1). No data sent unless you explicitly enable AI.  
✓ **CSV data never written to disk**: Datasets remain in memory only; never persisted to storage.  
✓ **Metadata-only audit**: SQLite audit history stores only dataset names, timestamps, row/column counts, cleaning changes—never raw cell values.  
✓ **Aggregate-only AI**: If AI is enabled, only statistical summaries sent (row counts, missing counts, numeric summaries); never raw CSV rows or personal data.  
✓ **No code execution**: Chat commands use deterministic regex parsing only; no `eval()`, `exec()`, or arbitrary Python allowed.  
✓ **Formula injection protection**: Dangerous spreadsheet cell prefixes (=, +, -, @) automatically escaped with apostrophe to prevent formula execution.  
✓ **Safe SQL**: Only SELECT queries allowed; INSERT, UPDATE, DELETE, DROP, ALTER, and other dangerous keywords blocked at parse time.  
✓ **Environment-only API keys**: Never embedded in code; always read from environment variables, never logged.  
✓ **Windows privacy compliance**: Runs locally, no phone-home telemetry, no external dependencies for core functionality, XSRF protection enabled.

---

## Feature Matrix

| Feature | Auto Mode | Manual (Pandas ✓) | Manual (NumPy ✗) | Manual (SQL ✗) |
|---------|-----------|-------------------|------------------|-----------------|
| Cleaning & Profiling | ✓ | ✓ | ✓ | ✓ |
| Chat Changes | ✓ | ✓ | ✓ | ✓ |
| Correlation Analysis | ✓ | ✓ | ✗ | ✓ |
| Segmentation & Sampling | ✓ | ✓ | ✗ | ✓ |
| Validation Rules | ✓ | ✓ | ✗ | ✓ |
| SQL Queries | ✓ | ✓ | ✓ | ✗ |
| Audit History | ✓ | ✓ | ✓ | ✗ |
| AI Insights | ✓ | ✓ | ✓ | ✓ |

---

## Troubleshooting

- **"ModuleNotFoundError: No module named..."**: Run `run_windows.bat` or manually activate the virtual environment and run `pip install -r requirements.txt`.
- **Port 8501 already in use**: Stop the previous Streamlit instance or change the port in `.streamlit/config.toml` (`server.port = 8502`).
- **Large CSV takes a long time**: Memory is limited by your available RAM. Consider filtering the CSV before upload or processing in chunks.
- **AI requests fail**: Check that environment variables (AI_PROVIDER, API_KEY, etc.) are set before starting `streamlit run app.py`.
- **"Only SELECT allowed"**: The SQL validator blocks INSERT, UPDATE, DELETE, and other write operations to protect your data.

---

## Questions?

See [`PRIVACY.md`](PRIVACY.md) for detailed privacy and security documentation. For feature requests or bug reports, refer to your local project documentation.
