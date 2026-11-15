import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

from .constants import VLM_MAX_PAGES, CVResponseError, CVVisionUnavailable
from .llm_extract import _parse_cv_text
from .normalization import (
    _build_import_report,
    _has_usable_content,
    _locate_evidence,
    _merge_cv_complement,
    _pages_with_text,
    is_empty_extraction,
)
from .pdf_io import pdf_pages_all_blank


def _pkg():
    return sys.modules[__package__]


async def _complete_with_remaining_pages(
    vlm_payload: Dict[str, Any],
    page_texts: Optional[List[str]],
    model: str,
    usages: List[Dict[str, Any]],
    errors: List[str],
) -> List[int]:
    """Complète le résultat VLM avec le texte des pages au-delà de VLM_MAX_PAGES."""
    pkg = _pkg()
    if page_texts is None:
        return []
    text_pages = _pages_with_text(page_texts, VLM_MAX_PAGES + 1)
    if not text_pages:
        return []
    try:
        pkg.logger.info("Complément texte du CV pour les pages au-delà de %d", VLM_MAX_PAGES)
        extra = await _parse_cv_text("\n\n".join(page_texts[VLM_MAX_PAGES:]), model)
        usages.extend(extra.pop("_usage", None) or [])
        _merge_cv_complement(vlm_payload, extra)
        return text_pages
    except Exception as exc:
        usages.extend(getattr(exc, "usage", None) or [])
        pkg.logger.warning("Échec du complément texte des pages restantes du CV : %s", exc)
        errors.append(
            f"Les pages au-delà de la page {VLM_MAX_PAGES} n'ont pas pu être analysées : "
            "leur contenu n'est pas dans le profil importé."
        )
        return []


async def parse_cv_with_llm(
    cv_text: str = "",
    pdf_path: Optional[str] = None,
    model: Optional[str] = None,
    vlm_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Extrait les données structurées du CV (VLM prioritaire puis repli LLM texte)."""
    pkg = _pkg()
    chosen_model = model or pkg.DEFAULT_CV_PARSER_MODEL
    chosen_vlm = vlm_model or pkg.DEFAULT_VLM_MODEL

    usages: List[Dict[str, Any]] = []
    errors: List[str] = []
    vlm_answered = False
    vlm_error: Optional[BaseException] = None
    has_pdf = bool(pdf_path and os.path.exists(pdf_path))
    page_texts: Optional[List[str]] = None

    if has_pdf:
        try:
            page_texts = await asyncio.to_thread(pkg.extract_page_texts, pdf_path)
        except Exception as exc:
            pkg.logger.warning(
                "Lecture page par page du PDF impossible, rapport de couverture omis : %s", exc
            )

    def report(
        payload: Dict[str, Any], vlm_pages: List[int], text_pages: List[int], fallback: bool
    ) -> Optional[Dict[str, Any]]:
        if page_texts is None:
            return None
        evidence = _locate_evidence(payload, page_texts)
        return _build_import_report(len(page_texts), vlm_pages, text_pages, fallback, errors, evidence)

    if has_pdf:
        try:
            if await asyncio.to_thread(pdf_pages_all_blank, pdf_path):
                vlm_answered = True
                images: List[str] = []
                pkg.logger.info("PDF sans contenu visible : analyse visuelle ignorée")
            else:
                images = await asyncio.to_thread(pkg.render_pdf_pages_to_base64_images, pdf_path)

            if images and os.environ.get("MISTRAL_API_KEY"):
                pkg.logger.info("Extraction du CV via VLM (%s) sur %d page(s)", chosen_vlm, len(images))
                vlm_payload = await pkg.parse_cv_with_vlm(images, model=chosen_vlm)
                vlm_answered = True
                if isinstance(vlm_payload, dict):
                    usages.extend(vlm_payload.pop("_usage", None) or [])
                if _has_usable_content(vlm_payload):
                    pkg.logger.info("Succès de l'extraction VLM pour le CV")
                    text_pages = await _complete_with_remaining_pages(
                        vlm_payload, page_texts, chosen_model, usages, errors
                    )
                    vlm_payload["_usage"] = usages
                    built = report(vlm_payload, list(range(1, len(images) + 1)), text_pages, False)
                    if built is not None:
                        vlm_payload["_import_report"] = built
                    return vlm_payload
                pkg.logger.warning("Réponse VLM vide pour le CV, bascule vers le LLM texte")
                errors.append(
                    "L'analyse visuelle n'a rien renvoyé : le texte extrait du PDF a été utilisé à la place."
                )
        except Exception as exc:
            vlm_error = exc
            usages.extend(getattr(exc, "usage", None) or [])
            pkg.logger.warning("Échec de l'extraction VLM du CV, bascule vers le LLM texte : %s", exc)
            errors.append(
                "L'analyse visuelle a échoué : le texte extrait du PDF a été utilisé à la place."
            )

    if not cv_text and has_pdf:
        cv_text = await asyncio.to_thread(pkg.extract_text_from_pdf, pdf_path)

    if not cv_text.strip():
        if has_pdf and not vlm_answered:
            raise CVVisionUnavailable(usage=usages) from vlm_error
        empty: Dict[str, Any] = {
            "headline": "", "summary": "", "experiences": [], "projects": [],
            "education": [], "certifications": [], "skills": {},
        }
        if usages:
            empty["_usage"] = usages
        built = report(empty, [], [], has_pdf)
        if built is not None:
            empty["_import_report"] = built
        return empty

    try:
        data = await _parse_cv_text(cv_text, chosen_model)
    except CVResponseError as exc:
        exc.usage = usages + exc.usage
        raise
    data["_usage"] = usages + data.get("_usage", [])
    if has_pdf and not vlm_answered and is_empty_extraction(data):
        raise CVVisionUnavailable(usage=data["_usage"]) from vlm_error
    built = report(data, [], _pages_with_text(page_texts or []), has_pdf)
    if built is not None:
        data["_import_report"] = built
    return data
