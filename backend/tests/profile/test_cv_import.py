"""Import de CV PDF : rejets explicites, usage unique, rapport éphémère, panne du VLM."""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cv_parser import CVResponseError


def test_uploaded_file_is_deleted_after_parsing(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")

    async def fake_parse(_text):
        return {"headline": "Ingénieur Data", "skills": {"outils": ["Python"]}}

    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)

    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(_pdf_bytes("blank")), "application/pdf")},
    )
    assert res.status_code == 200
    assert list(tmp_path.iterdir()) == []
    assert profile_db["sources"]["cv"]["headline"] == "Ingénieur Data"


def _pdf_bytes(kind: str) -> bytes:
    import fitz
    if kind == "unreadable":
        return b"%PDF-1.7 octets corrompus"
    doc = fitz.open()
    if kind.startswith("scanned") or kind == "mixed":  # page image ; "scanned_text" garde un numéro de page en texte
        if kind == "mixed":  # une page de texte, puis une page scannée
            doc.new_page(width=200, height=200).insert_text((20, 50), "Contact", fontsize=14)
        source = fitz.open()
        source.new_page(width=200, height=200).insert_text((20, 50), "CV scanné", fontsize=14)
        page = doc.new_page(width=200, height=200)
        page.insert_image(page.rect, pixmap=source[0].get_pixmap(dpi=72))
        if kind == "scanned_text":
            page.insert_text((20, 190), "Page 1/1", fontsize=8)
        source.close()
    else:
        doc.new_page()
    options = {"encryption": fitz.PDF_ENCRYPT_AES_256, "user_pw": "secret", "owner_pw": "owner"} if kind == "protected" else {}
    try:
        return doc.tobytes(**options)
    finally:
        doc.close()


@pytest.mark.parametrize("kind, expected", [
    ("protected", "mot de passe"), ("unreadable", "illisible"), ("blank", "Aucun contenu exploitable"),
])
def test_unusable_pdf_is_rejected_without_profile_or_usage(client, profile_db, monkeypatch, tmp_path, kind, expected):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path / "up"))
    record = AsyncMock()
    async def fake_parse(_text, pdf_path=None):
        if kind != "blank":
            raise AssertionError("aucun appel LLM pour un PDF protégé ou illisible")
        return {"headline": "", "experiences": [], "skills": {}, "_usage": [{"model": "m1", "input_tokens": 700}]}

    monkeypatch.setattr(router, "record_api_usage", record)
    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)
    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(_pdf_bytes(kind)), "application/pdf")},
    )
    assert res.status_code == 400
    assert expected in res.json()["detail"]
    assert profile_db == {}
    record.assert_not_called()


def test_cv_import_records_a_single_usage_entry(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router

    usage = [{"model": "m1", "input_tokens": 10, "output_tokens": 1},
             {"model": "m2", "input_tokens": 20, "output_tokens": 2},
             {"model": "m1", "input_tokens": 5, "output_tokens": 1}]

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")
    recorded = []

    async def fake_record(**kwargs):
        recorded.append(kwargs)

    async def fake_parse(_text, pdf_path=None):
        return {"headline": "Ingénieur Data", "skills": {"outils": ["Python"]}, "_usage": usage}

    monkeypatch.setattr(router, "record_api_usage", fake_record)
    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)

    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(_pdf_bytes("blank")), "application/pdf")},
    )
    assert res.status_code == 200
    assert len(recorded) == 1
    assert recorded[0]["models_used"] == ["m1", "m2"]
    assert recorded[0]["input_tokens"] == 35
    assert recorded[0]["output_tokens"] == 4
    assert recorded[0]["estimated_cost_usd"] >= 0


IMPORT_REPORT = {
    "total_pages": 5,
    "pages_by_method": {"vlm": [1, 2, 3], "text": [4]},
    "skipped_pages": [5],
    "fallback_used": False,
    "errors": ["Message lisible"],
}


def test_cv_import_returns_report_but_never_persists_it(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")

    async def fake_parse(_text, pdf_path=None):
        return {"headline": "Ingénieur Data", "skills": {"outils": ["Python"]}, "_import_report": dict(IMPORT_REPORT)}

    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)

    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(_pdf_bytes("blank")), "application/pdf")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["import_report"] == IMPORT_REPORT
    assert body["headline"] == "Ingénieur Data"
    assert "_import_report" not in body
    stored_cv = profile_db["sources"]["cv"]
    assert "_import_report" not in stored_cv and "import_report" not in stored_cv
    assert "import_report" not in profile_db and "_import_report" not in profile_db


@pytest.mark.parametrize("kind, vlm_answers, status, message, text_llm_called", [
    ("scanned", False, 503, "VISION_UNAVAILABLE_MESSAGE", False),
    ("scanned_text", False, 503, "VISION_UNAVAILABLE_MESSAGE", True),
    # Le VLM répond sans rien trouver : fichier vide (400), pas une panne.
    ("mixed", True, 400, "EMPTY_CV_MESSAGE", True),
])
def test_empty_scanned_import_is_503_on_vlm_outage_and_400_when_vlm_answers_empty(
    client, profile_db, monkeypatch, tmp_path, kind, vlm_answers, status, message, text_llm_called
):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key")
    record = AsyncMock()
    monkeypatch.setattr(router, "record_api_usage", record)
    # Réponse VLM invalide mais facturée : un coût existe, la route ne doit pas l'enregistrer.
    billed = [{"model": "mistral/ministral-14b-2512", "input_tokens": 900, "output_tokens": 20}]
    empty_text_answer = MagicMock(
        choices=[MagicMock(message=MagicMock(content="{}"))], usage=MagicMock(prompt_tokens=10, completion_tokens=2)
    )
    vlm_outcome = {"return_value": {}} if vlm_answers else {"side_effect": CVResponseError("JSON invalide", billed)}
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, **vlm_outcome):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=empty_text_answer) as llm:
            res = client.post(
                "/profile/candidate/sources/cv",
                files={"file": ("cv.pdf", io.BytesIO(_pdf_bytes(kind)), "application/pdf")},
            )
    assert res.status_code == status
    assert res.json()["detail"] == getattr(router, message)
    assert profile_db == {}
    record.assert_not_called()
    assert llm.called is text_llm_called
