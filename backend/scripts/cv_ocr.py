"""OCR Mistral pour le banc de comparaison de l'import de CV (scripts uniquement, jamais dans ``app/``).

Schéma : POST https://api.mistral.ai/v1/ocr, ``document`` de type ``document_url``, réponse
``pages[].markdown`` et ``usage_info.pages_processed`` (docs.mistral.ai, vérifié le 2026-11-08).
Prix : 2 $ / 1000 pages pour ``mistral-ocr-2512``.
"""

import base64
import os
from typing import List, Tuple

import httpx

OCR_URL = "https://api.mistral.ai/v1/ocr"
OCR_MODEL = "mistral-ocr-2512"
OCR_USD_PER_PAGE = 0.002
OCR_TIMEOUT_S = 120.0


def ocr_pdf(path: str, model: str = OCR_MODEL) -> Tuple[List[str], int]:
    """Texte OCR de chaque page du PDF et nombre de pages facturées. Appel réseau réel."""
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY absent : OCR impossible")
    with open(path, "rb") as f:
        data_url = "data:application/pdf;base64," + base64.b64encode(f.read()).decode("ascii")
    response = httpx.post(
        OCR_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "document": {"type": "document_url", "document_url": data_url}},
        timeout=OCR_TIMEOUT_S,
    )
    if response.is_error:
        raise RuntimeError(f"OCR {response.status_code} : {response.text[:300]}")
    response.raise_for_status()
    body = response.json()
    pages = sorted(body.get("pages") or [], key=lambda p: p.get("index", 0))
    texts = [p.get("markdown") or "" for p in pages]
    processed = (body.get("usage_info") or {}).get("pages_processed") or len(texts)
    return texts, int(processed)
