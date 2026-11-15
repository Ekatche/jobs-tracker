from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.llm.utils import clean_cookie_banners, summarize_chunks
from job_crawler.crawler1 import COOKIE_DISMISS_JS


@pytest.mark.parametrize(
    ("raw_text", "expected_absent", "expected_present"),
    [
        (
            "Nous utilisons des cookies pour améliorer.\n\nData Scientist - Diagnoly",
            "Nous utilisons des cookies",
            "Data Scientist - Diagnoly",
        ),
        (
            "We use cookies to enhance your browsing experience.\n"
            "Necessary cookies are required to enable the basic features.\n"
            "  * CookieYes sets this cookie for consent solution management.\n\n"
            "Diagnoly is an early-stage DeepTech start-up.",
            "CookieYes",
            "Diagnoly is an early-stage DeepTech start-up.",
        ),
        (
            "Analytical cookies are used to understand how visitors interact.\n"
            "  * 1 year 1 month 4 days\n"
            "  * Google Analytics sets this cookie to store and count page views.\n\n"
            "Missions: Build deep learning algorithms.",
            "Analytical cookies",
            "Missions: Build deep learning algorithms.",
        ),
        (
            "Data Engineer — Work on HTTP cookies & session security in Python.",
            "CookieYes",
            "HTTP cookies & session security",
        ),
    ],
)
def test_clean_cookie_banners(raw_text: str, expected_absent: str, expected_present: str):
    cleaned = clean_cookie_banners(raw_text)
    assert expected_absent not in cleaned
    assert expected_present in cleaned


def test_cookie_dismiss_js_covers_cookieyes():
    assert 'button[data-cky-tag="accept-button"]' in COOKIE_DISMISS_JS
    assert ".cky-btn-accept" in COOKIE_DISMISS_JS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("llm_reply", "expected_result"),
    [
        ("1. RÉSUMÉ : Diagnoly recrute un Data Scientist.", "1. RÉSUMÉ : Diagnoly recrute un Data Scientist."),
        ("AUCUNE_OFFRE", ""),
    ],
)
async def test_summarize_chunks_strips_cookie_banner_offline(
    monkeypatch, llm_reply: str, expected_result: str
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured = {}

    class FakeChain:
        async def ainvoke(self, payload):
            captured["text"] = payload["text"]
            return SimpleNamespace(content=llm_reply, usage_metadata={})

    fake_prompt = MagicMock()
    fake_prompt.__or__ = MagicMock(return_value=FakeChain())

    docs = [
        Document(
            page_content=(
                "We use cookies to enhance your browsing experience.\n"
                "  * CookieYes sets this cookie for consent solution management.\n\n"
                "Diagnoly is a DeepTech start-up in Lyon hiring a Data Scientist."
            )
        )
    ]

    with patch("app.llm.utils.PromptTemplate", return_value=fake_prompt), patch(
        "app.llm.utils.ChatOpenAI", return_value=MagicMock()
    ):
        result = await summarize_chunks(docs)

    assert "CookieYes" not in captured["text"]
    assert "Diagnoly" in captured["text"]
    assert result == expected_result
