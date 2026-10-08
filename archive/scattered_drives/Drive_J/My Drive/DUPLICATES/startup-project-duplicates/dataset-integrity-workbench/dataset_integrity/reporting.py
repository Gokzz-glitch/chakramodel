"""Optional, bounded Gemini summaries with schema validation."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Mapping, Optional, Sequence

from .integrations import OptionalDependencyError, require

DEFAULT_GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.5-pro")


def configured_models(models: Sequence[str] = ()) -> tuple[str, ...]:
    """Return a de-duplicated, non-empty model list without contacting Gemini."""
    selected = tuple(dict.fromkeys(model.strip() for model in models if model.strip()))
    return selected or DEFAULT_GEMINI_MODELS


def summarize_report(report: Mapping[str, Any], max_records: int = 50, max_chars: int = 12000) -> dict[str, Any]:
    payload = {
        "summary": report.get("summary", {}),
        "duplicates": report.get("duplicates", [])[:max_records],
        "changes": report.get("changes", [])[:max_records],
        "errors": report.get("errors", [])[:max_records],
    }
    encoded = json.dumps(payload, sort_keys=True)
    if len(encoded) > max_chars:
        encoded = encoded[:max_chars]
    return {"summary": payload["summary"], "evidence": encoded}


def gemini_report(report: Mapping[str, Any], model: str = "gemini-2.5-flash",
                  retries: int = 3, max_chars: int = 12000) -> dict[str, Any]:
    if not os.environ.get("GEMINI_API_KEY"):
        raise OptionalDependencyError("GEMINI_API_KEY is not configured")
    require("gemini")
    from google import genai  # type: ignore

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = json.dumps(summarize_report(report, max_chars=max_chars), sort_keys=True)
    last_error: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        try:
            response = client.models.generate_content(
                model=model,
                contents="Return JSON with keys risk_level, findings, recommendations. Evidence:\n" + prompt,
                config={"response_mime_type": "application/json"},
            )
            parsed = json.loads(response.text)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("findings", []), list):
                raise ValueError("Gemini response failed schema validation")
            parsed.setdefault("risk_level", "unknown")
            parsed.setdefault("recommendations", [])
            return parsed
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            last_error = exc
            if attempt + 1 < max(1, retries):
                time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("Gemini reporting failed after retries") from last_error
