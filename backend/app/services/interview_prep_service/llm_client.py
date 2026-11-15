"""Shared LLM invocation, usage tracking, and JSON parsing for interview prep."""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Union

from bson import ObjectId

from app.models import ApiUsageAction

# `letter_llm` vit hors du package `app` (même montage que profile/collectors/website.py).
_JOB_TRACKERS_SRC = Path(__file__).resolve().parents[3] / "job_trackers" / "src" / "job_trackers"
if str(_JOB_TRACKERS_SRC) not in sys.path:
    sys.path.insert(0, str(_JOB_TRACKERS_SRC))

# GPT-5 et Claude 5 rejettent `temperature` : build_completion_kwargs l'omet pour eux.
from letter_llm import build_completion_kwargs  # noqa: E402

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts" / "interview"
DEFAULT_INTERVIEW_MODEL = os.getenv(
    "INTERVIEW_PREP_MODEL", os.getenv("EVALUATION_MODEL", "gemini/gemini-3.8-flash")
)


def _pkg() -> Any:
    """Resolve package facade dynamically so test patches on package attributes apply."""
    return sys.modules["app.services.interview_prep_service"]


def _clean_json_output(raw_text: str) -> Union[Dict[str, Any], List[Any]]:
    """Strip markdown code block fences and parse JSON object or array."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Tenter de trouver le premier tableau ou objet JSON valide
        match_arr = re.search(r"(\[.*\])", cleaned, flags=re.DOTALL)
        if match_arr:
            try:
                return json.loads(match_arr.group(1))
            except json.JSONDecodeError:
                pass
        match_obj = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if match_obj:
            try:
                return json.loads(match_obj.group(1))
            except json.JSONDecodeError:
                pass
        raise


async def call_interview_llm(
    db: Any,
    user_id: Union[str, ObjectId],
    offer: Dict[str, Any],
    template_name: str,
    sub_action: str,
    format_vars: Dict[str, Any],
) -> Union[Dict[str, Any], List[Any]]:
    """Render an interview prompt template, invoke LLM, log usage, and parse JSON output."""
    pkg = _pkg()
    model = pkg.DEFAULT_INTERVIEW_MODEL
    template = (pkg.PROMPTS_DIR / template_name).read_text(encoding="utf-8")
    prompt = template.format(**format_vars)

    t0 = time.time()
    response = await pkg.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        drop_params=True,
        **build_completion_kwargs(model, 0.2),
    )
    latency_ms = int((time.time() - t0) * 1000)

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    await pkg.record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.INTERVIEW_PREP,
        models_used=[model],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=True,
        metadata={"sub_action": sub_action, "offer_id": str(offer.get("_id", ""))},
    )

    return _clean_json_output(response.choices[0].message.content)
