import pathlib
import re
import sys
from pathlib import Path

import pytest

# Ensure job_trackers source is importable
job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

import cover_letter_crew

PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "app" / "llm" / "prompts" / "cover_letter"

def test_prompt_files_exist_and_not_empty():
    expected_files = ["01_fond.md", "02_style.md", "03_critique.md", "04_revision.md"]
    for fname in expected_files:
        fpath = PROMPTS_DIR / fname
        assert fpath.exists(), f"Missing prompt file: {fname}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 100, f"Prompt {fname} is too short or empty"

def test_prompt_critique_does_not_duplicate_banned_lexicon():
    critique_content = (PROMPTS_DIR / "03_critique.md").read_text(encoding="utf-8")
    assert "solide expertise" not in critique_content.lower()
    assert "pass" in critique_content.lower()
    assert "revise" in critique_content.lower()


def test_writer_prompt_is_loaded_from_file():
    rendered = cover_letter_crew.load_prompt(
        "02_style",
        candidate_name="",
        candidate_headline="",
        company_name="Acme",
        min_words=cover_letter_crew.MIN_WORDS,
        max_words=cover_letter_crew.MAX_WORDS,
        missions="['Pipelines']",
        experiences="[]",
        stacks="Python",
        projects="",
        capped_repetitions="test",
        company_context_block="",
        voice_style_block="",
    )
    assert "Acme" in rendered
    assert "{company_name}" not in rendered


def test_no_identity_is_hardcoded_in_the_module():
    """Aucun nom de personne ou d'employeur ne doit vivre dans le code."""
    source = open(cover_letter_crew.__file__, encoding="utf-8").read()
    for forbidden in ("Eliel Katche", "Agence Nile", "Centre Léon Bérard", "Bimedoc"):
        assert forbidden not in source, f"{forbidden} codé en dur dans le crew"


def test_prompt_files_have_no_identity_either():
    for name in ("01_fond", "02_style", "03_critique", "04_revision"):
        content = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        assert "Eliel Katche" not in content
