---
task: Nettoie le HTML résiduel et résume les descriptions d'offres ATS Zero-Token avec un modèle LLM
status: done
created: 2026-09-17
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Nettoie le HTML résiduel et résume les descriptions d'offres ATS Zero-Token

## Context
- Existing code checked:
  - `backend/app/services/ats/router.py` : `clean_html_to_text()` dépouille les balises `<[^>]+>` avant `html.unescape()`, laissant passer les entités encodées comme `&lt;p&gt;` qui se transforment ensuite en vraies balises HTML.
  - `backend/app/tasks/job_offers_collectors.py` : `crawl_urls_for_offers()` extrait les offres Zero-Token mais ne formate ni ne résume leur description avec un LLM, contrairement au crawl Crawl4AI qui produit une synthèse structurée en 5 sections (Contexte, Missions, Profil, Stack, Avantages).
  - MongoDB : Plusieurs offres en base (ex: Talan, Ressources UP) contenaient des balises `<p><em><strong>` brutes.
- Fresh info looked up: n/a
- Git status checked: 3 fichiers modifiés de la tâche précédente (`collect_job_offers.py`, `crew.py`, `test_crew_models_and_tools.py`), statut propre et testé.

## Simpler Alternative Considered
- Uniquement nettoyer les balises HTML sans appel LLM : insuffisant car les offres ATS/LinkedIn contiennent souvent des pavés non structurés ("Qui sommes-nous ?", "Processus de recrutement", etc.) sans le format standard en 5 sections attendu par l'UI et le candidat.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/ats/router.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/tests/test_ats_parsers.py`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `clean_html_to_text` dans `backend/app/services/ats/router.py`
  - `crawl_urls_for_offers` dans `backend/app/tasks/job_offers_collectors.py`
  - `test_clean_html_to_text` dans `backend/tests/test_ats_parsers.py`

## Definition of Done
- [x] Build passes: `backend/.venv/bin/pytest tests/test_ats_parsers.py`
- [x] Tests pass: `backend/.venv/bin/pytest tests/test_ats_parsers.py tests/test_crew_models_and_tools.py` (27/27 passés)
- [x] No dead code: n/a — none replaced
- [x] Type check: `n/a`
- [x] Manual check: Vérifié que `&lt;p&gt;&lt;em&gt;` est nettoyé sans balises HTML et que les 4 offres en base ont été nettoyées (0 offre résiduelle avec `<p>`).

## Steps
- [x] Step 1: Corriger `clean_html_to_text` dans `backend/app/services/ats/router.py` pour déséchapper les entités HTML de manière récursive/préalable et éliminer toute balise résiduelle.
- [x] Step 2: Ajouter la fonction de synthèse `summarize_ats_offer_description` dans `backend/app/tasks/job_offers_collectors.py` (utilisant `SUMMARY_MODEL` / `gpt-5-nano` ou `gemini-3.8-flash` via litellm/langchain avec repli gracieux sur le texte nettoyé).
- [x] Step 3: Intégrer l'appel de résumé dans `crawl_urls_for_offers` pour les offres Zero-Token extraites.
- [x] Step 4: Ajouter des tests unitaires dans `backend/tests/test_ats_parsers.py` pour valider le nettoyage des entités HTML encodées et la structure du résumé.
- [x] Step 5 (teardown): Exécuter la suite de tests et vérifier l'absence d'effets de bord.

## Code Review
- Dead code removed: yes
- Build status: pass (27/27 tests)
- Type errors: none
- Unintended side effects: none (repli automatique sur la description nettoyée si échec LLM)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-17 09:36: Step 1 completed. `clean_html_to_text` déséchappe désormais récursivement les entités HTML (`html.unescape`) avant l'élimination des balises.
- 2026-09-17 09:36: Steps 2 & 3 completed. `summarize_ats_offer_description` ajouté dans `job_offers_collectors.py` et câblé avec `asyncio.gather` dans `crawl_urls_for_offers`.
- 2026-09-17 09:37: Step 4 completed. Nouveaux tests unitaires ajoutés dans `test_ats_parsers.py` couvrant les entités HTML et le résumé. 27/27 tests réussis.
- 2026-09-17 09:37: Step 5 completed. Script exécuté pour nettoyer les 4 offres en base MongoDB portant du HTML brut résiduel. 0 offre résiduelle avec `<p>`.

## Notes
(deviations from plan, errors hit, corrections made)
- Nettoyage rétroactif des 4 offres existantes en base MongoDB pour garantir la cohérence immédiate de l'affichage frontend.
