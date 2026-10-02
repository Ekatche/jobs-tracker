"""La constante frontend reprend le registre backend : mêmes clés, même ordre, mêmes couleurs."""
import re
from pathlib import Path

import pytest

from app.services.cv_templates import CV_ACCENTS, CV_TEMPLATES, CV_TEMPLATES_WITHOUT_PHOTO

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
CONSTANT_FILE = FRONTEND_DIR / "src" / "lib" / "cvTemplates.ts"


@pytest.fixture
def source():
    if not FRONTEND_DIR.exists():
        pytest.skip("frontend absent (conteneur backend seul)")
    return CONSTANT_FILE.read_text(encoding="utf-8")


def test_template_keys_match_registry(source):
    keys = re.findall(r'key: "([a-z_]+)",\s*label: "[^"]+",\s*hint:', source)
    assert tuple(keys) == CV_TEMPLATES


def test_photo_support_matches_registry(source):
    entries = re.findall(r'key: "([a-z_]+)",[^}]*supportsPhoto: (true|false)', source)
    assert {key for key, value in entries if value == "false"} == set(CV_TEMPLATES_WITHOUT_PHOTO)


def test_accent_colors_match_registry(source):
    pairs = re.findall(r'key: "([a-z_]+)", label: "[^"]+", primary: "(#[0-9a-f]{6})"', source)
    assert dict(pairs) == {key: colors["primary"] for key, colors in CV_ACCENTS.items()}
