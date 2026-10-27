import base64
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import pymupdf as fitz
except ImportError:
    import fitz

import httpx

from app.services.egress_guard import public_only_transport
from app.services.profile.urls import reject_non_public_request

logger = logging.getLogger(__name__)

# Maximum file size to download (25 MB) to avoid memory exhaustion
MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024
DEFAULT_PDF_TIMEOUT = 15.0

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
}

KNOWN_CONTRACT_PATTERNS = [
    (r"\b(CDI|Contrat à durée indéterminée)\b", "CDI"),
    (r"\b(CDD|Contrat à durée déterminée)\b", "CDD"),
    (r"\b(Stage|Stagiaire|Internship)\b", "Stage"),
    (r"\b(Alternance|Apprentissage|Contrat de professionnalisation)\b", "Alternance"),
    (r"\b(Freelance|Indépendant|Prestation)\b", "Freelance"),
    (r"\b(Intérim|Mission d'intérim)\b", "Intérim"),
]


def is_pdf_url(url: str) -> bool:
    """Checks whether the given URL points directly to a PDF file by extension."""
    if not url or not isinstance(url, str):
        return False
    try:
        path = urlparse(url).path.lower()
        return path.endswith(".pdf")
    except Exception:
        return False


async def check_is_pdf_content(url: str, timeout: float = 5.0) -> bool:
    """Fast check to see if a URL serves a PDF, either by extension or Content-Type header."""
    if is_pdf_url(url):
        return True

    if not url or not url.startswith(("http://", "https://")):
        return False

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
            event_hooks={"request": [reject_non_public_request]},
            transport=public_only_transport(),
        ) as client:
            resp = await client.head(url)
            content_type = resp.headers.get("content-type", "").lower()
            return "application/pdf" in content_type or "application/x-pdf" in content_type
    except Exception as e:
        logger.debug(f"HEAD check failed for PDF content on {url}: {e}")
        return False


async def download_pdf_bytes(
    url: str,
    max_size_bytes: int = MAX_PDF_SIZE_BYTES,
    timeout: float = DEFAULT_PDF_TIMEOUT,
) -> Optional[bytes]:
    """Downloads the raw bytes of a remote PDF with strict size and timeout guards."""
    if not url or not url.startswith(("http://", "https://")):
        logger.warning(f"Invalid URL for PDF download: {url}")
        return None

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
            event_hooks={"request": [reject_non_public_request]},
            transport=public_only_transport(),
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"PDF download failed with status {resp.status_code} for {url}")
                return None

            content_type = resp.headers.get("content-type", "").lower()
            # If not explicitly PDF by URL and header is not PDF, discard
            if not is_pdf_url(url) and "pdf" not in content_type:
                logger.warning(f"URL {url} responded with non-PDF content-type: {content_type}")
                return None

            content = resp.content
            if len(content) > max_size_bytes:
                logger.error(
                    f"PDF size {len(content)} exceeds maximum limit {max_size_bytes} for {url}"
                )
                return None

            if len(content) < 32:
                logger.warning(f"PDF content too short ({len(content)} bytes) for {url}")
                return None

            return content
    except Exception as e:
        logger.error(f"Error while downloading PDF from {url}: {e}")
        return None


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts raw text from PDF bytes using PyMuPDF (fitz)."""
    if not pdf_bytes:
        return ""

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text: List[str] = []
    try:
        for page in doc:
            text = page.get_text()
            if text and text.strip():
                pages_text.append(text.strip())
        raw_combined = "\n\n".join(pages_text)
        # Normalize redundant blank lines
        clean_combined = re.sub(r"\n{3,}", "\n\n", raw_combined).strip()
        return clean_combined
    except Exception as e:
        logger.error(f"Error extracting text from PDF stream: {e}")
        return ""
    finally:
        doc.close()


def render_pdf_bytes_to_base64_images(
    pdf_bytes: bytes, max_pages: int = 3, dpi: int = 150
) -> List[str]:
    """Renders PDF pages to base64-encoded PNG images for visual language model (VLM) fallback."""
    if not pdf_bytes:
        return []

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: List[str] = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes("png")
            images.append(base64.b64encode(png_bytes).decode("utf-8"))
        return images
    except Exception as e:
        logger.error(f"Error rendering PDF pages to images: {e}")
        return []
    finally:
        doc.close()


def detect_offer_metadata_from_text(text: str, url: str = "") -> Dict[str, Optional[str]]:
    """Extracts basic metadata heuristically from text and filename hint."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    contract: Optional[str] = None

    # Detect contract type
    for pattern, label in KNOWN_CONTRACT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            contract = label
            break

    # Look for common French job posting headers
    for i, line in enumerate(lines[:30]):
        # Match "Poste : ...", "Intitulé : ...", "Emploi : ..."
        m_poste = re.search(r"^(?:intitulé du poste|poste proposé|poste|emploi)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if m_poste and not title:
            title = m_poste.group(1).strip()

        # Match "Établissement : ...", "Entreprise : ...", "Société : ..."
        m_company = re.search(r"^(?:établissement|entreprise|société|association|structure)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if m_company and not company:
            company = m_company.group(1).strip()

        # Match "Lieu : ...", "Ville : ...", "Localisation : ..."
        m_loc = re.search(r"^(?:lieu|ville|localisation|secteur)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if m_loc and not location:
            location = m_loc.group(1).strip()

    # Fallback title from the first prominent non-trivial line if still None
    if not title and lines:
        for line in lines[:5]:
            if len(line) >= 5 and len(line) <= 100:
                # Exclude purely metadata words
                if not re.match(r"^(offre d'emploi|fiche de poste|recrutement|avis de vacance)$", line, re.IGNORECASE):
                    title = line
                    break

    # Fallback title from URL filename if nothing cleaner was found
    if not title and url:
        try:
            filename = urlparse(url).path.split("/")[-1].replace(".pdf", "")
            title = re.sub(r"[-_]+", " ", filename).strip()
        except Exception:
            pass

    return {
        "title": title,
        "company": company,
        "location": location,
        "contract": contract,
    }


async def _transcribe_scanned_pdf_with_vlm(pdf_bytes: bytes) -> str:
    """Fallback transcription for scanned/image-only PDFs via Vision LLM."""
    try:
        from litellm import acompletion
    except ImportError:
        logger.warning("litellm not available for PDF VLM transcription")
        return ""

    images = render_pdf_bytes_to_base64_images(pdf_bytes, max_pages=3, dpi=150)
    if not images:
        return ""

    model = os.getenv("VLM_MODEL", os.getenv("FAST_LLM_MODEL", "gemini/gemini-2.5-flash"))
    logger.info(f"Transcribing scanned PDF using VLM model: {model} ({len(images)} pages)")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Tu es un extracteur d'offre d'emploi. Retranscris fidèlement l'intégralité "
                        "du texte de cette offre d'emploi en conservant la structure, l'intitulé du poste, "
                        "l'entreprise, le lieu, le contrat, les missions, et le profil requis."
                    ),
                },
                *[
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"},
                    }
                    for img in images
                ],
            ],
        }
    ]

    try:
        response = await acompletion(
            model=model,
            messages=messages,
            temperature=0.0,
            max_tokens=2500,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"VLM transcription failed: {e}")
        return ""


async def extract_pdf_job_offer(
    url: str,
    pdf_bytes: Optional[bytes] = None,
    timeout: float = DEFAULT_PDF_TIMEOUT,
) -> Optional[Dict[str, Any]]:
    """Extracts job offer text and metadata from a PDF URL or provided raw bytes."""
    if pdf_bytes is None:
        pdf_bytes = await download_pdf_bytes(url, timeout=timeout)

    if not pdf_bytes:
        logger.warning(f"Could not retrieve PDF bytes for {url}")
        return None

    # Step 1: Zero-token direct text extraction with PyMuPDF
    text = extract_text_from_pdf_bytes(pdf_bytes)

    # Step 2: If the text is empty or minimal (e.g. scanned document), fallback to VLM
    if len(text.strip()) < 100:
        logger.info(f"PDF text too sparse ({len(text)} chars), attempting VLM transcription for {url}")
        vlm_text = await _transcribe_scanned_pdf_with_vlm(pdf_bytes)
        if vlm_text and len(vlm_text.strip()) >= 50:
            text = vlm_text

    if not text or len(text.strip()) < 20:
        logger.warning(f"No usable content could be extracted from PDF {url}")
        return None

    meta = detect_offer_metadata_from_text(text, url=url)

    return {
        "text": text,
        "title": meta.get("title") or "Offre d'emploi",
        "company": meta.get("company"),
        "location": meta.get("location"),
        "contract": meta.get("contract"),
        "url": url,
        "word_count": len(text.split()),
        "raw_char_count": len(text),
    }
