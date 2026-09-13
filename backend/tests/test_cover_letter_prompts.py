import pathlib
import pytest

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
