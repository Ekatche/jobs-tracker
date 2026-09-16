import io
import pytest
from unittest.mock import AsyncMock, patch

from app.services.cv_parser import (
    extract_text_from_pdf,
    render_pdf_pages_to_base64_images,
    parse_cv_with_vlm,
    parse_cv_with_llm,
)


def _create_sample_pdf():
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((20, 50), "John Doe\nSenior Data Engineer\nPython, Docker, FastAPI", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_render_pdf_pages_to_base64_images(tmp_path):
    pdf_bytes = _create_sample_pdf()
    pdf_file = tmp_path / "sample_cv.pdf"
    pdf_file.write_bytes(pdf_bytes)

    images = render_pdf_pages_to_base64_images(str(pdf_file), max_pages=2)
    assert len(images) == 1
    assert isinstance(images[0], str)
    assert len(images[0]) > 50  # Base64 string of the PNG rendering


def test_extract_text_from_pdf(tmp_path):
    pdf_bytes = _create_sample_pdf()
    pdf_file = tmp_path / "sample_cv.pdf"
    pdf_file.write_bytes(pdf_bytes)

    text = extract_text_from_pdf(str(pdf_file))
    assert "John Doe" in text
    assert "Senior Data Engineer" in text


@pytest.mark.asyncio
async def test_parse_cv_with_vlm_raises_without_images():
    with pytest.raises(ValueError, match="Aucune image"):
        await parse_cv_with_vlm([])


@pytest.mark.asyncio
async def test_parse_cv_with_vlm_calls_litellm_with_images():
    fake_response = AsyncMock()
    fake_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"headline": "Lead ML Engineer", "summary": "Expert IA", "experiences": [], "skills": {"languages": ["Python"]}}'
            )
        )
    ]

    with patch("app.services.cv_parser.acompletion", return_value=fake_response) as mock_acompletion:
        result = await parse_cv_with_vlm(
            base64_images=["fake_base64_png"],
            model="mistral/pixtral-12b-2409",
            api_key="test-key",
        )

        assert result["headline"] == "Lead ML Engineer"
        assert result["skills"]["languages"] == ["Python"]
        assert mock_acompletion.call_count == 1
        call_kwargs = mock_acompletion.call_args[1]
        assert call_kwargs["model"] == "mistral/pixtral-12b-2409"
        messages = call_kwargs["messages"]
        assert len(messages[0]["content"]) == 2
        assert messages[0]["content"][1]["type"] == "image_url"


@pytest.mark.asyncio
async def test_parse_cv_with_llm_falls_back_to_text_on_vlm_error(tmp_path, monkeypatch):
    pdf_bytes = _create_sample_pdf()
    pdf_file = tmp_path / "sample_cv.pdf"
    pdf_file.write_bytes(pdf_bytes)

    monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key")

    fake_text_response = AsyncMock()
    fake_text_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"headline": "Fallback Data Engineer", "summary": "Fallback", "experiences": [], "skills": {}}'
            )
        )
    ]

    # Simuler un échec VLM
    with patch("app.services.cv_parser.parse_cv_with_vlm", side_effect=RuntimeError("VLM connection failed")):
        with patch("app.services.cv_parser.acompletion", return_value=fake_text_response):
            result = await parse_cv_with_llm(pdf_path=str(pdf_file))
            assert result["headline"] == "Fallback Data Engineer"
