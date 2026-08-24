from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

import pandas as pd


def build_profile_context(profile: dict[str, Any]) -> dict[str, Any]:
    numeric = profile["numeric_summary"]
    numeric_summary = {}
    if not numeric.empty:
        numeric_summary = {
            str(column): {
                key: float(value) if pd.notna(value) else None
                for key, value in row.items()
                if key in {"count", "mean", "std", "min", "25%", "50%", "75%", "max"}
            }
            for column, row in numeric.iterrows()
        }
    return {
        "rows": profile["rows"],
        "columns": profile["columns"],
        "missing_cells": profile["missing_cells"],
        "duplicate_rows": profile["duplicate_rows"],
        "missing_by_column": {str(key): int(value) for key, value in profile["missing_by_column"].items()},
        "outliers": {str(key): int(value) for key, value in profile["outliers"].items()},
        "numeric_summary": numeric_summary,
    }


def request_ai_interpretation(
    profile: dict[str, Any],
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    provider = os.getenv("AI_PROVIDER", "openai").lower()
    if os.getenv("AI_ALLOW_EXTERNAL", "false").lower() != "true":
        raise RuntimeError("External AI is disabled. Set AI_ALLOW_EXTERNAL=true only after confirming the provider's billing and free-tier settings.")

    if provider == "omniroute":
        api_key = api_key or os.getenv("OMNIROUTE_API_KEY")
        base_url = (base_url or os.getenv("OMNIROUTE_BASE_URL", "")).rstrip("/")
        model = os.getenv("OMNIROUTE_MODEL", "")
        if not base_url or not model:
            raise RuntimeError("For Omniroute, set OMNIROUTE_BASE_URL and OMNIROUTE_MODEL.")
    else:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        raise RuntimeError(f"Set the {provider.upper()} API key in the environment. Never put it in source code or commit it.")
    context = json.dumps(build_profile_context(profile), ensure_ascii=True)
    prompt = (
        "Interpret this dataset quality profile for an analyst. Return concise sections titled "
        "Key findings, Risks, Recommended actions, and Caveats. Do not invent facts. "
        "Only use the supplied aggregate statistics; mention when evidence is limited.\n\n"
        f"Profile: {context}"
    )
    payload = json.dumps({
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You are a careful data-quality analyst."},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    http_request = request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"AI service rejected the request ({exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach the configured AI service: {exc.reason}") from exc

    try:
        return str(result["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("The AI service returned an unexpected response") from exc
