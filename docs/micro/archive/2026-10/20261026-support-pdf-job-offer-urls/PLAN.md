---
task: Support PDF job offer URLs in application ingestion and downstream tools
description: Ingestion d'offres d'emploi au format PDF via URL (PyMuPDF fitz, détection d'URL/Content-Type, fetch_documents dans backend/app/llm/utils.py, intégration crawler1.py et liaison job_offers pour CV adapté, lettre de motivation et scoring)
status: done
created: 2026-10-26
---

# Support PDF Job Offer URLs

## Context
- Existing code checked:
  - `backend/app/llm/utils.py` : `fetch_documents(url)` n'interceptait que les ATS et déléguait à Crawl4AI (Chromium), qui échoue sur les fichiers PDF directs.
  - `backend/app/services/cv_parser.py` : utilise déjà `fitz` (PyMuPDF) pour extraire le texte et générer des images base64 pour VLM.
  - `backend/app/routers/applications.py` : `_generate_description_bg` appelle `fetch_documents(url)`, découpe et résume avec le LLM, puis lie l'offre via `_ensure_offer_for_application`.
  - `backend/job_crawler/crawler1.py` : `crawl_and_extract_jobs_optimized` et `get_filtered_markdown` ne géraient pas les liens PDF.
- Fresh info looked up:
  - PyMuPDF (`fitz.open(stream=bytes, filetype="pdf")`) validé sur le PDF utilisateur (`5305` caractères extraits en <0.05s sans consommation de tokens).
- Git status checked: clean (tracked files).

## Simpler Alternative Considered
- Laisser Chromium télécharger le PDF et tenter un parsing HTML : non viable, Chromium headless en mode stream/markdown ne produit pas de texte structuré exploitable pour les PDF statiques. L'extraction directe via `PyMuPDF` (`fitz`) est 100x plus rapide, sans token et déterministe.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/pdf_job_offer.py` (nouveau service d'extraction PDF)
  - `backend/app/llm/utils.py` (interception PDF dans `fetch_documents`)
  - `backend/job_crawler/crawler1.py` (support PDF direct dans `get_filtered_markdown` et `crawl_and_extract_jobs_optimized`)
  - `backend/tests/test_pdf_offer_ingestion.py` (nouveaux tests unitaires et d'intégration)
- **Files NOT touched**:
  - `backend/app/services/cv_tailor.py` (fonctionne déjà dès que `description` est présente)
  - `backend/app/routers/cover_letters.py` (inchangé)
  - `backend/app/routers/applications.py` (inchangé, bénéficie de `fetch_documents`)
  - Tous les composants frontend (NewApplicationModal, Kanban, etc.)
- **Symbols replaced**: none
- **Symbols extended**:
  - `fetch_documents` in `backend/app/llm/utils.py` (ajout du branchement PDF prioritaire)
  - `get_filtered_markdown` in `backend/job_crawler/crawler1.py` (détection PDF anticipée)
  - `crawl_and_extract_jobs_optimized` in `backend/job_crawler/crawler1.py` (gestion des URLs PDF)

## Definition of Done
- [x] Build passes: `cd backend && ./.venv/bin/python -m py_compile app/services/pdf_job_offer.py app/llm/utils.py job_crawler/crawler1.py`
- [x] Tests pass: `cd backend && ./.venv/bin/pytest tests/test_pdf_offer_ingestion.py -v`
- [x] Regression tests pass: `cd backend && ./.venv/bin/pytest tests/test_ats_parsers.py tests/test_application_offer_link.py -v`
- [x] No dead code: `cd backend && ./.venv/bin/python -c "from app.services.pdf_job_offer import is_pdf_url, extract_pdf_job_offer; print('Imports ok')"`
- [x] Manual check: simulation d'ingestion sur l'URL de test Fondation Prado avec vérification du Document retourné (> 1000 caractères, métadonnées complètes)

## Steps
- [x] Step 1: Créer le module `backend/app/services/pdf_job_offer.py` avec `is_pdf_url`, `download_pdf_bytes`, `extract_text_from_pdf_bytes`, et `extract_pdf_job_offer`.
- [x] Step 2: Intégrer l'extraction PDF dans `fetch_documents` (`backend/app/llm/utils.py`) avant l'appel à Crawl4AI.
- [x] Step 3: Intégrer la détection PDF dans `get_filtered_markdown` et `crawl_and_extract_jobs_optimized` (`backend/job_crawler/crawler1.py`) pour la régénération d'offres.
- [x] Step 4: Écrire les tests unitaires et d'intégration dans `backend/tests/test_pdf_offer_ingestion.py` avec fixtures PDF réelles et mockées.
- [x] Step 5 (teardown): Vérifier la suppression de tout code temporaire ou orphelin, valider la suite de tests et les types.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: yes (taille max de téléchargement limitée à 25 Mo pour prévenir les bombes PDF / OOM, timeout HTTP 15s)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-26T17:57Z | antigravity | step 1 | started
- 2026-10-26T17:58Z | antigravity | step 1 | done | `app/services/pdf_job_offer.py` created & py_compile exit 0
- 2026-10-26T17:58Z | antigravity | step 2 | started
- 2026-10-26T17:59Z | antigravity | step 2 | done | `fetch_documents` returned 5298 chars Document for Fondation Prado PDF exit 0
- 2026-10-26T17:59Z | antigravity | step 3 | started
- 2026-10-26T18:01Z | antigravity | step 3 | done | `get_filtered_markdown` extracted 5298 chars from PDF URL exit 0
- 2026-10-26T18:01Z | antigravity | step 4 | started
- 2026-10-26T18:01Z | antigravity | step 4 | done | `pytest tests/test_pdf_offer_ingestion.py` 7 passed exit 0
- 2026-10-26T18:01Z | antigravity | step 5 | started
- 2026-10-26T18:03Z | antigravity | step 5 | done | teardown check & all DoD items passed fresh exit 0
- 2026-10-26T18:03Z | antigravity | closeout | done | status done

## Notes
- Baseline: regression tests `tests/test_ats_parsers.py` et `tests/test_application_offer_link.py` passent (25 passed).
- Pour les PDF scannés sans couche de texte, un fallback VLM basé sur `render_pdf_pages_to_base64_images` (déjà éprouvé dans `cv_parser.py`) est prévu si le nombre de caractères extraits est inférieur à 100.
