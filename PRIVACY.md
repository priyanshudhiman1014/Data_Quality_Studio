# Privacy and Security

Data Quality Studio is designed to run locally on Windows.

- The Streamlit server binds to `127.0.0.1`; it is not exposed to your network by default.
- Streamlit usage statistics are disabled.
- Uploaded CSV contents are processed in memory and are not copied to disk by the application.
- SQLite stores only dataset filename, timestamps, row/column counts, cleaning changes, and quality metrics. It does not store CSV rows or column values.
- The generated SQLite file is local and should be protected like any other local application data.
- The upload limit is 500 MB to reduce resource-exhaustion risk while supporting large local datasets.
- Multiple CSV files can be selected; their total upload size is limited to 500 MB and rows retain a `source_file` label.
- Downloaded filenames are sanitized to prevent path traversal.
- Formula-like text values are prefixed in exported CSVs to reduce spreadsheet formula-injection risk.
- AI interpretation is disabled unless `AI_ALLOW_EXTERNAL=true` is explicitly configured, along with a provider API key. When enabled, only aggregate profiling statistics are sent to the configured OpenAI-compatible service; raw CSV rows are not sent.
- Users must also manually enable **Enable external AI** in the sidebar for the current app session. The switch defaults to off and prevents the AI request button from being available while off.
- The application does not generate or manage API keys, and cannot guarantee that a provider account is free. Check Omniroute's current plan, model pricing, quotas, and billing controls before enabling external calls.
- The application does not authenticate users. Use it only on a trusted Windows account and do not change the bind address unless you understand the network exposure.

This is an operational privacy design, not a legal guarantee or a substitute for an organization’s formal privacy review. Do not upload regulated or confidential data unless your organization has approved local processing and the Windows device is appropriately secured.
