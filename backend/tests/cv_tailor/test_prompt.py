
from app.services.cv_tailor import (
    PAGE_BUDGETS,
    compute_page_budget,
)
from tests.cv_tailor.fixtures import SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION


def test_load_tailor_prompt_includes_bloc_b_requirements_with_weight():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "Aucune analyse Bloc B préalable disponible." not in prompt
    assert "- Python [critical] (Preuve: Tech Corp senior backend)" in prompt
    assert "- Docker [meaningful, couverture partielle] (Preuve: Profile skill)" in prompt
    assert "- Kubernetes [high] (Écart: Aucune mention d'orchestration de conteneurs)" in prompt


def test_load_tailor_prompt_french_job_offer_fields():
    from app.services.cv_tailor import load_tailor_prompt

    french_offer = {
        "poste": "Ingénieure / Ingénieur IA",
        "entreprise": "DeepTech France",
        "localisation": "Paris (Télétravail)",
        "description": "Poste orienté frameworks d'agents et LLM.",
    }
    prompt = load_tailor_prompt(SAMPLE_PROFILE, french_offer)

    assert "DeepTech France" in prompt
    assert "Ingénieure / Ingénieur IA" in prompt
    assert "Paris (Télétravail)" in prompt
    assert "Poste visé" not in prompt
    assert "L'entreprise cible" not in prompt


def test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "vocabulaire technique" not in prompt
    assert "vocabulaire métier" in prompt
    assert "colis ou lignes par heure" in prompt
    assert "délai de recrutement" in prompt
    assert "antichronologique" in prompt
    assert "CACES" in prompt
    budget = compute_page_budget(SAMPLE_PROFILE)
    assert f"Budget total : {budget.bullets} puces" in prompt
    assert f"0 à {budget.projects} projets" in prompt
    assert ("Deux pages A4" if budget.pages == 2 else "Une page A4") in prompt
    assert "{page_limit}" not in prompt
    assert '"relevance": "principale ou secondaire"' in prompt


def test_load_tailor_prompt_renders_one_and_two_page_budgets():
    from app.services.cv_tailor import load_tailor_prompt

    junior = {**SAMPLE_PROFILE, "experiences": [{"title": "Dev", "company": "A", "start_date": "2019-01", "end_date": "2022-01"}]}
    prompt = load_tailor_prompt(junior, SAMPLE_OFFER)

    assert "Une page A4" in prompt
    assert "0 à 2 projets" in prompt
    assert f"Budget total : {PAGE_BUDGETS[1].bullets} puces" in prompt

    experienced = {**SAMPLE_PROFILE, "experiences": [{"title": "Dev", "company": "A", "start_date": "2016-01", "end_date": "2021-01"}]}
    prompt = load_tailor_prompt(experienced, SAMPLE_OFFER)

    assert "Deux pages A4" in prompt
    assert "0 à 3 projets" in prompt
    assert f"Budget total : {PAGE_BUDGETS[2].bullets} puces" in prompt


def test_load_tailor_prompt_asks_for_short_sober_summary():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "expert mondial" not in prompt
    assert "percutante" not in prompt
    assert "proposition de valeur" not in prompt
    assert "45 mots" not in prompt
    assert prompt.count("70 mots") >= 2
    assert "expérience éprouvée" in prompt
    assert "habitué à" in prompt
    assert "Ne cite aucun nom d'employeur" in prompt


def test_load_tailor_prompt_grounds_summary_in_profile_experiences():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "guident la première phrase" not in prompt
    assert "Positionne le candidat" not in prompt
    assert "N'emprunte à l'offre aucun terme" in prompt
    assert "doit se retrouver dans le profil" in prompt
    assert "livrable ou public" in prompt
    assert "Reste général" in prompt
    assert "Scientist spécialisé" not in prompt
    assert "d'expérience dans" in prompt
    assert "Avec Python" not in prompt
    assert prompt.count("principalement en") == 0
    assert "Ne cite jamais le permis de conduire dans l'accroche" in prompt


def test_load_tailor_prompt_without_evaluation_judges_relevance_from_offer():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER)

    assert "Aucune analyse Bloc B préalable disponible." in prompt
    assert "En l'absence d'analyse Bloc B, juge la pertinence de chaque expérience d'après l'offre" in prompt


def test_load_tailor_prompt_injects_seniority_phrase():
    from app.services.cv_tailor import load_tailor_prompt, compute_page_budget

    profile_8yrs = {
        "full_name": "Camille Martin",
        "experiences": [{"start": "09/2018", "end": "09/2026", "title": "Éducatrice"}]
    }
    offer = {"poste": "Éducateur Spécialisé", "entreprise": "Association Horizon"}
    budget = compute_page_budget(profile_8yrs)
    prompt = load_tailor_prompt(profile_8yrs, offer, budget=budget)

    assert "avec 8 ans d'expérience dans" in prompt

    profile_junior = {
        "full_name": "Junior Dev",
        "experiences": [{"start": "01/2026", "end": "06/2026", "title": "Stagiaire"}]
    }
    budget_j = compute_page_budget(profile_junior)
    prompt_j = load_tailor_prompt(profile_junior, offer, budget=budget_j)

    assert "avec une expérience dans" in prompt_j
