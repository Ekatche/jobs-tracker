"""Import de CV PDF : rejets explicites, usage unique, rapport éphémère, panne du VLM."""
import io
from unittest.mock import AsyncMock

import pytest


def test_uploaded_file_is_deleted_after_parsing(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")

    async def fake_parse(_text):
        return {"headline": "Ingénieur Data", "experiences": []}

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


@pytest.mark.parametrize(
    "usage,expected_models,expected_in,expected_out",
    [
        ([{"model": "m1", "input_tokens": 10, "output_tokens": 1},
          {"model": "m2", "input_tokens": 20, "output_tokens": 2},
          {"model": "m1", "input_tokens": 5, "output_tokens": 1}], ["m1", "m2"], 35, 4),
        ({"model": "m1", "input_tokens": 7, "output_tokens": 3}, ["m1"], 7, 3),
    ],
)
def test_cv_import_records_a_single_usage_entry(
    client, profile_db, monkeypatch, tmp_path, usage, expected_models, expected_in, expected_out
):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")
    recorded = []

    async def fake_record(**kwargs):
        recorded.append(kwargs)

    async def fake_parse(_text, pdf_path=None):
        return {"headline": "Ingénieur Data", "experiences": [], "_usage": usage}

    monkeypatch.setattr(router, "record_api_usage", fake_record)
    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)

    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(_pdf_bytes("blank")), "application/pdf")},
    )
    assert res.status_code == 200
    assert len(recorded) == 1
    assert recorded[0]["models_used"] == expected_models
    assert recorded[0]["input_tokens"] == expected_in
    assert recorded[0]["output_tokens"] == expected_out
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
        return {"headline": "Ingénieur Data", "experiences": [], "_import_report": dict(IMPORT_REPORT)}

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



def _scanned_pdf_bytes() -> bytes:
    """PDF d'une seule image, sans couche texte."""
    import fitz
    source, doc = fitz.open(), fitz.open()
    source.new_page(width=200, height=200).insert_text((20, 50), "CV scanné", fontsize=14)
    doc.new_page(width=200, height=200).insert_image(fitz.Rect(0, 0, 200, 200), pixmap=source[0].get_pixmap(dpi=72))
    try:
        return doc.tobytes()
    finally:
        source.close()
        doc.close()


def test_vlm_outage_on_scanned_pdf_is_a_503_without_storage_or_usage(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router
    from unittest.mock import patch

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key")
    record = AsyncMock()
    monkeypatch.setattr(router, "record_api_usage", record)
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, side_effect=Exception("429")):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock) as llm:
            res = client.post(
                "/profile/candidate/sources/cv",
                files={"file": ("cv.pdf", io.BytesIO(_scanned_pdf_bytes()), "application/pdf")},
            )
    assert res.status_code == 503
    assert res.json()["detail"] == router.VISION_UNAVAILABLE_MESSAGE
    assert profile_db == {}
    record.assert_not_called()
    llm.assert_not_called()
