"""Couverture de l'import PDF : pages au-delà de la limite VLM, VLM vide ou invalide,
suivi de l'usage facturable (tests hors réseau, fournisseurs simulés)."""
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

VLM_OK = {
    "headline": "Data Engineer",
    "summary": "Résumé VLM",
    "experiences": [{"company": "Acme", "role": "Data Engineer", "start": "2020"}],
    "skills": {"outils": ["Python"]},
    "contact": {"mobility": ""},
    "_usage": [{"model": "mistral/pixtral-12b-2409", "input_tokens": 100, "output_tokens": 50}],
}


def _make_pdf(tmp_path, pages: int, scanned: frozenset = frozenset(), texts: Optional[List[str]] = None):
    """PDF de test ; les pages de `scanned` sont une image sans couche texte.

    `texts` fixe le texte (une ligne par élément séparé par \\n) de chaque page, sinon un marqueur."""
    import fitz

    doc = fitz.open()
    for i in range(1, pages + 1):
        page = doc.new_page(width=300, height=300)
        if i in scanned:
            source = fitz.open()
            source.new_page(width=300, height=300).insert_text((20, 50), texts[i - 1] if texts else f"SCAN_{i}", fontsize=14)
            page.insert_image(page.rect, pixmap=source[0].get_pixmap(dpi=72))
            source.close()
        else:
            page.insert_text((20, 50), texts[i - 1] if texts else f"MARQUEUR_PAGE_{i}", fontsize=14)
    path = tmp_path / "cv.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _llm_response(content: str, prompt_tokens=10, completion_tokens=5):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    resp.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return resp


@pytest.fixture
def mistral_key(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy-key")


def _vlm_payload(**overrides):
    payload = {**VLM_OK, "_usage": list(VLM_OK["_usage"])}
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_pages_beyond_vlm_limit_are_completed_from_text(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 4)
    complement = _llm_response(
        '{"headline": "Autre titre", "summary": "Autre", "skills": {"outils": ["Docker"]},'
        ' "experiences": [{"company": "Beta", "role": "Dev", "start": "2018"}]}'
    )
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=_vlm_payload()):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=complement) as llm:
            result = await parse_cv_with_llm(cv_text="texte complet", pdf_path=pdf)

    prompt = llm.call_args.kwargs["messages"][0]["content"]
    assert "MARQUEUR_PAGE_4" in prompt
    assert "MARQUEUR_PAGE_1" not in prompt and "MARQUEUR_PAGE_3" not in prompt
    assert result["headline"] == "Data Engineer"  # le VLM n'est pas écrasé
    assert [e["company"] for e in result["experiences"]] == ["Acme", "Beta"]
    assert result["skills"]["outils"] == ["Python", "Docker"]
    assert [u["model"] for u in result["_usage"]] == ["mistral/pixtral-12b-2409", "openai/gpt-4o-mini"]


@pytest.mark.asyncio
async def test_no_complement_call_for_three_pages(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 3)
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=_vlm_payload()):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock) as llm:
            result = await parse_cv_with_llm(cv_text="texte", pdf_path=pdf)

    llm.assert_not_called()
    assert len(result["_usage"]) == 1


@pytest.mark.asyncio
async def test_complement_failure_keeps_vlm_result(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 4)
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=_vlm_payload()):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            result = await parse_cv_with_llm(cv_text="texte", pdf_path=pdf)

    assert result["headline"] == "Data Engineer"
    assert len(result["experiences"]) == 1


@pytest.mark.parametrize(
    "empty_payload",
    [
        {"headline": "", "experiences": [], "skills": {}},
        {"headline": "  ", "experiences": [{}], "skills": {"outils": []}},
        {},
    ],
)
@pytest.mark.asyncio
async def test_empty_vlm_response_falls_back_to_text_and_keeps_usage(tmp_path, mistral_key, empty_payload):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 1)
    payload = {**empty_payload, "_usage": list(VLM_OK["_usage"])}
    fallback = _llm_response('{"headline": "Repli texte", "experiences": [], "skills": {}}')
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=payload):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=fallback):
            result = await parse_cv_with_llm(cv_text="texte du CV", pdf_path=pdf)

    assert result["headline"] == "Repli texte"
    assert [u["model"] for u in result["_usage"]] == ["mistral/pixtral-12b-2409", "openai/gpt-4o-mini"]


@pytest.mark.asyncio
async def test_invalid_vlm_json_still_reports_billed_usage(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 1)
    invalid = _llm_response("ceci n'est pas du JSON", prompt_tokens=700, completion_tokens=20)
    fallback = _llm_response('{"headline": "Repli texte", "experiences": [], "skills": {}}')
    with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, side_effect=[invalid, fallback]):
        result = await parse_cv_with_llm(cv_text="texte du CV", pdf_path=pdf)

    assert result["headline"] == "Repli texte"
    vlm_usage, text_usage = result["_usage"]
    assert (vlm_usage["input_tokens"], vlm_usage["output_tokens"]) == (700, 20)
    assert text_usage["model"] == "openai/gpt-4o-mini"


@pytest.mark.parametrize(
    "base,extra,expected",
    [
        ({"interests": ["Judo"]}, {"interests": ["judo", "Piano"]}, {"interests": ["Judo", "Piano"]}),
        ({"skills": {"a": ["Python"]}}, {"skills": {"a": ["python", "SQL"], "b": ["Git"]}},
         {"skills": {"a": ["Python", "SQL"], "b": ["Git"]}}),
        ({"summary": "VLM"}, {"summary": "Texte"}, {"summary": "VLM"}),
        ({"summary": ""}, {"summary": "Texte"}, {"summary": "Texte"}),
        ({"contact": {"mobility": "Permis B"}}, {"contact": {"mobility": "X", "availability": "2x8"}},
         {"contact": {"mobility": "Permis B", "availability": "2x8"}}),
        ({"education": [{"school": "UTC", "degree": "Ingénieur"}]},
         {"education": [{"school": "utc", "degree": "ingénieur"}]},
         {"education": [{"school": "UTC", "degree": "Ingénieur"}]}),
    ],
)
def test_merge_cv_complement_never_overwrites(base, extra, expected):
    from app.services.cv_parser import _merge_cv_complement

    merged = _merge_cv_complement(base, extra)
    for key, value in expected.items():
        assert merged[key] == value


COMPLEMENT_JSON = '{"headline": "", "experiences": [], "skills": {}, "summary": "Suite"}'


def _assert_report_partitions_pages(report):
    """Invariant : vlm U text U skipped = toutes les pages, sans recouvrement."""
    vlm, text = report["pages_by_method"]["vlm"], report["pages_by_method"]["text"]
    everything = vlm + text + report["skipped_pages"]
    assert sorted(everything) == list(range(1, report["total_pages"] + 1))
    assert len(everything) == len(set(everything))


@pytest.mark.asyncio
async def test_report_vlm_pages_text_complement_and_scanned_skip(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 6, scanned=frozenset({2, 6}))  # 2 : vue par le VLM ; 6 : scannée au-delà
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=_vlm_payload()):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock,
                   return_value=_llm_response(COMPLEMENT_JSON)):
            result = await parse_cv_with_llm(cv_text="texte", pdf_path=pdf)

    report = result["_import_report"]
    assert report == {
        "total_pages": 6,
        "pages_by_method": {"vlm": [1, 2, 3], "text": [4, 5]},
        "skipped_pages": [6],
        "fallback_used": False,
        "errors": [],
        "evidence": [],
    }
    _assert_report_partitions_pages(report)


@pytest.mark.asyncio
async def test_report_full_text_fallback_skips_scanned_pages(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 4, scanned=frozenset({2}))
    fallback = _llm_response('{"headline": "Repli", "experiences": [], "skills": {}}')
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock,
               side_effect=RuntimeError("secret technique")):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=fallback):
            result = await parse_cv_with_llm(cv_text="texte du CV", pdf_path=pdf)

    report = result["_import_report"]
    assert report["fallback_used"] is True
    assert report["pages_by_method"] == {"vlm": [], "text": [1, 3, 4]}
    assert report["skipped_pages"] == [2]
    assert len(report["errors"]) == 1 and "secret technique" not in report["errors"][0]
    _assert_report_partitions_pages(report)


@pytest.mark.asyncio
async def test_report_complement_failure_skips_pages_beyond_limit(tmp_path, mistral_key):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 5)
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=_vlm_payload()):
        with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            result = await parse_cv_with_llm(cv_text="texte", pdf_path=pdf)

    report = result["_import_report"]
    assert report["pages_by_method"] == {"vlm": [1, 2, 3], "text": []}
    assert report["skipped_pages"] == [4, 5]
    assert report["fallback_used"] is False
    assert len(report["errors"]) == 1 and "boom" not in report["errors"][0]
    _assert_report_partitions_pages(report)


@pytest.mark.asyncio
async def test_report_without_mistral_key_marks_fallback(tmp_path, monkeypatch):
    from app.services.cv_parser import parse_cv_with_llm

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    pdf = _make_pdf(tmp_path, 2)
    fallback = _llm_response('{"headline": "Repli", "experiences": [], "skills": {}}')
    with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=fallback):
        result = await parse_cv_with_llm(cv_text="texte du CV", pdf_path=pdf)

    assert result["_import_report"]["fallback_used"] is True
    assert result["_import_report"]["pages_by_method"] == {"vlm": [], "text": [1, 2]}


@pytest.mark.asyncio
async def test_no_report_without_pdf():
    from app.services.cv_parser import parse_cv_with_llm

    fallback = _llm_response('{"headline": "Texte", "experiences": [], "skills": {}}')
    with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=fallback):
        result = await parse_cv_with_llm(cv_text="texte du CV")

    assert "_import_report" not in result


@pytest.mark.parametrize(
    "base,extra,expected",
    [
        ({"experiences": [{"company": "Acme", "role": "Data Engineer", "start": "2020"}]},
         {"experiences": [{"company": "Acme", "role": "Data Analyst", "start": "2020"}]},
         {"experiences": [{"company": "Acme", "role": "Data Engineer", "start": "2020"},
                          {"company": "Acme", "role": "Data Analyst", "start": "2020"}]}),
        ({"experiences": [{"company": "Acme", "role": "Data Engineer", "start": "09/2021"}]},
         {"experiences": [{"company": "ACME", "role": "data engineer", "start": "2021-09"}]},
         {"experiences": [{"company": "Acme", "role": "Data Engineer", "start": "09/2021"}]}),
        ({"experiences": [{"company": "Acme", "role": "Data Engineer"}]},
         {"experiences": [{"company": "Acme", "role": "Data Engineer", "start": None}]},
         {"experiences": [{"company": "Acme", "role": "Data Engineer"}]}),
        ({"education": [{"school": "UTC", "degree": "Ingénieur"}], "languages": ["Anglais (C1)"]},
         {"education": [{"school": "UTC", "degree": "Ingénieur"}], "languages": ["Anglais (C1)"]},
         {"education": [{"school": "UTC", "degree": "Ingénieur"}], "languages": ["Anglais (C1)"]}),
    ],
)
def test_merge_cv_complement_keeps_distinct_experiences_and_dedups_the_rest(base, extra, expected):
    from app.services.cv_parser import _merge_cv_complement

    merged = _merge_cv_complement(base, extra)
    assert {section: merged[section] for section in expected} == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "texts, company, scanned, page, excerpt",
    [
        (["Profil data", "Initech - Data Engineer"], "Initech", frozenset(), 2, "Initech - Data Engineer"),
        (["Profil data", "Initech - Data Engineer"], "Initech", frozenset({2}), None, None),
        # Mot entier et ligne exacte : « Acmeology » ne vaut pas « Acme », l'extrait est la 2e ligne.
        (["Acmeology Labs\nAcme - Data Engineer", "Fin"], "Acme", frozenset(), 1, "Acme - Data Engineer"),
        (["Acmeology Labs", "Fin"], "Acme", frozenset(), None, None),
    ],
)
async def test_evidence_points_to_the_page_text_never_to_a_scan(tmp_path, mistral_key, texts, company, scanned, page, excerpt):
    from app.services.cv_parser import parse_cv_with_llm

    pdf = _make_pdf(tmp_path, 2, scanned=scanned, texts=texts)
    vlm = _vlm_payload(experiences=[{"company": company, "role": "Data Engineer", "start": "2020"}])
    with patch("app.services.cv_parser.parse_cv_with_vlm", new_callable=AsyncMock, return_value=vlm):
        result = await parse_cv_with_llm(cv_text="texte", pdf_path=pdf)

    evidence = result["_import_report"]["evidence"]
    if page is None:
        assert evidence == []
    else:
        assert [(e["section"], e["index"], e["page"], e["excerpt"]) for e in evidence] == [("experiences", 0, page, excerpt)]
