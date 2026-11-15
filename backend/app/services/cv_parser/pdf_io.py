import base64
import sys
from typing import List

from .constants import VLM_MAX_PAGES


def _pkg():
    return sys.modules[__package__]


def extract_page_texts(pdf_path: str) -> List[str]:
    """Texte brut de chaque page d'un PDF (chaîne vide pour une page sans couche texte)."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def extract_text_from_pdf(pdf_path: str, start_page: int = 0) -> str:
    """Extrait le texte brut d'un PDF (à partir de la page d'index start_page)."""
    return "\n\n".join(_pkg().extract_page_texts(pdf_path)[start_page:])


def is_pdf_readable(pdf_path: str) -> bool:
    """Vrai si le PDF s'ouvre et contient au moins une page."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return False
    try:
        return doc.page_count > 0
    finally:
        doc.close()


def is_pdf_password_protected(pdf_path: str) -> bool:
    """Vrai si le PDF exige un mot de passe d'ouverture."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return False
    try:
        return bool(doc.needs_pass)
    finally:
        doc.close()


def render_pdf_pages_to_base64_images(
    pdf_path: str, max_pages: int = VLM_MAX_PAGES, dpi: int = 150
) -> List[str]:
    """Rend les pages du PDF sous forme d'images PNG encodées en base64 pour analyse VLM."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    images: List[str] = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            png_bytes = page.get_pixmap(dpi=dpi).tobytes("png")
            images.append(base64.b64encode(png_bytes).decode("utf-8"))
        return images
    finally:
        doc.close()


def pdf_pages_all_blank(pdf_path: str, max_pages: int = VLM_MAX_PAGES, dpi: int = 15) -> bool:
    """Vrai si les pages envoyées au VLM sont toutes unicolores (PDF vierge)."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(pdf_path)
        try:
            if doc.page_count == 0:
                return False
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                if not page.get_pixmap(dpi=dpi).is_unicolor:
                    return False
            return True
        finally:
            doc.close()
    except Exception:
        return False
