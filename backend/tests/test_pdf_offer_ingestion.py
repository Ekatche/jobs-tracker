import io
import pytest
from unittest.mock import AsyncMock, patch

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from app.services.pdf_job_offer import (
    is_pdf_url,
    extract_text_from_pdf_bytes,
    detect_offer_metadata_from_text,
    extract_pdf_job_offer,
    download_pdf_bytes,
    MAX_PDF_SIZE_BYTES,
)
from app.llm.utils import fetch_documents
from job_crawler.crawler1 import get_filtered_markdown


def create_in_memory_pdf(content_lines: list) -> bytes:
    """Helper to generate a valid PDF byte string in-memory without external calls."""
    doc = fitz.open()
    page = doc.new_page()
    text = "\n".join(content_lines)
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_is_pdf_url():
    assert is_pdf_url("https://example.com/jobs/offer.pdf") is True
    assert is_pdf_url("https://example.com/jobs/offer.PDF") is True
    assert is_pdf_url("https://example.com/jobs/offer.pdf?ref=123") is True
    assert is_pdf_url("https://example.com/jobs/offer.html") is False
    assert is_pdf_url("https://example.com/jobs/offer") is False
    assert is_pdf_url("") is False
    assert is_pdf_url(None) is False


def test_extract_text_from_pdf_bytes():
    sample_lines = [
        "ÉDUCATEUR SPÉCIALISÉ (H/F)",
        "Établissement : Prado Isère",
        "Type de contrat : CDD",
        "Lieu : Grenoble",
        "Missions principales :",
        "- Accompagnement éducatif de jeunes",
        "- Travail en équipe pluridisciplinaire",
    ]
    pdf_bytes = create_in_memory_pdf(sample_lines)
    extracted = extract_text_from_pdf_bytes(pdf_bytes)

    assert "ÉDUCATEUR SPÉCIALISÉ" in extracted
    assert "Prado Isère" in extracted
    assert "CDD" in extracted
    assert "Grenoble" in extracted


def test_detect_offer_metadata_from_text():
    sample_text = (
        "ÉDUCATEUR SPÉCIALISÉ (H/F) REF607\n\n"
        "Établissement : Prado Isère Prévention Spécialisée\n"
        "Type de contrat : CDD\n"
        "Lieu : Isère\n"
        "Date limite : 18/10/2026\n\n"
        "Description du poste..."
    )
    meta = detect_offer_metadata_from_text(sample_text, url="https://example.com/Educateur-CDD-REF607.pdf")
    assert meta["contract"] == "CDD"
    assert meta["company"] == "Prado Isère Prévention Spécialisée"
    assert meta["location"] == "Isère"
    assert "ÉDUCATEUR SPÉCIALISÉ" in meta["title"]


@pytest.mark.asyncio
async def test_download_pdf_bytes_oversized_rejected():
    fake_oversized_bytes = b"0" * 100
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/pdf"}
        mock_resp.content = fake_oversized_bytes
        mock_get.return_value = mock_resp

        # Set max_size to smaller than content
        res = await download_pdf_bytes(
            "https://example.com/offer.pdf", max_size_bytes=50
        )
        assert res is None


@pytest.mark.asyncio
async def test_extract_pdf_job_offer_direct_bytes():
    sample_lines = [
        "POSTE PROPOSÉ : Responsable RH",
        "Entreprise : Solutec",
        "Type de contrat : CDI",
        "Ville : Lyon",
        "Missions : Gestion du personnel et recrutement.",
    ]
    pdf_bytes = create_in_memory_pdf(sample_lines)
    data = await extract_pdf_job_offer("https://example.com/job.pdf", pdf_bytes=pdf_bytes)

    assert data is not None
    assert "Responsable RH" in data["title"]
    assert data["company"] == "Solutec"
    assert data["contract"] == "CDI"
    assert data["location"] == "Lyon"
    assert len(data["text"]) > 50


@pytest.mark.asyncio
async def test_fetch_documents_intercepts_pdf_url():
    sample_lines = [
        "Développeur Fullstack Python React",
        "Entreprise : Startup Tech",
        "Contrat : CDI",
        "Nous recherchons un développeur motivé pour concevoir nos APIs.",
    ]
    pdf_bytes = create_in_memory_pdf(sample_lines)

    with patch("app.services.pdf_job_offer.download_pdf_bytes", return_value=pdf_bytes):
        docs = await fetch_documents("https://startup.com/jobs/fullstack.pdf")
        assert len(docs) == 1
        doc = docs[0]
        assert doc.metadata["content_type"] == "pdf"
        assert doc.metadata["source"] == "https://startup.com/jobs/fullstack.pdf"
        assert "Développeur Fullstack" in doc.page_content


@pytest.mark.asyncio
async def test_get_filtered_markdown_intercepts_pdf_url():
    sample_lines = [
        "Ingénieur Data Platform",
        "Entreprise : Cloud Services",
        "Type de contrat : CDI",
        "Missions : Mise en place de pipelines de données modernes.",
    ]
    pdf_bytes = create_in_memory_pdf(sample_lines)

    with patch("app.services.pdf_job_offer.download_pdf_bytes", return_value=pdf_bytes):
        result = await get_filtered_markdown("https://cloudservices.com/careers/data-engineer.pdf")
        assert result["status"] == "success"
        assert result["metadata"]["content_type"] == "pdf"
        assert "Ingénieur Data Platform" in result["filtered_markdown"]
