---
task: Implement Two-Pass AI Offer Evaluation pipeline (Blocks A-G, score 1.0-5.0) and detailed offer view (/offers/[id])
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Two-Pass AI Offer Evaluation Pipeline and Detailed View

## Context
- Existing code checked (inventaire complet) :
  - `backend/app/models.py`: `JobOffer` a les métadonnées de base mais aucun champ d'évaluation ni `pipeline_stage`. `CandidateProfile` et `CandidatePreferences` sont déjà opérationnels.
  - `backend/app/services/usage_tracker.py`: `ApiUsageAction.EVALUATION`, `require_user_quota()`, et `record_api_usage()` sont déjà prêts et testés.
  - `backend/app/llm/utils.py`: contient `summarize_chunks` pour le résumé de base, mais **aucun moteur d'évaluation Two-Pass n'est encore implémenté**.
  - `backend/app/routers/job_offers.py`: gère le CRUD des offres mais aucun endpoint d'évaluation.
  - `frontend/src/app/offers/`: contient la grille d'offres sans badge de score ni page de détail `/offers/[id]`.
- Fresh info looked up:
  - Career-Ops specification (`docs/CAREER_OPS_INTEGRATION_PLAN.md` §3 et `docs/SYSTEM_ARCHITECTURE.md` §3 & §6) :
    - Two-Pass Rule : Pass 1 (exigences & pondération de l'offre seule) → Pass 2 (croisement avec `CandidateProfile` et citations *verbatim*).
    - Blocs A à G : Bloc A (Résumé, Archétype, Drapeaux rouges), Bloc B (Match CV vs Offre avec verbatim), Bloc G (Intégrité/Ghost job).
    - Score final : float 1.0 à 5.0.
    - Quota : 20/mois (Free), 100/mois (Advanced), Illimité (Pro).
- Git status checked: clean on target backend and frontend files.

## Simpler Alternative Considered
- Évaluation basique en un seul prompt monolithique : **REJETÉ** car la règle des 2 passages (Two-Pass Rule) est formellement requise pour éviter les hallucinations d'exigences déduites à tort du CV et garantir des citations textuelles exactes (verbatim) du poste.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py` (modèles `OfferEvaluation`, `BlocA`, `BlocB`, `BlocG`, `RequirementMatch`, `MissingRequirement`, `JobOffer.pipeline_stage`)
  - `backend/app/services/evaluation/evaluator.py` (new - moteur Two-Pass LiteLLM avec prompt structuré et calcul de score)
  - `backend/app/routers/job_offers.py` (endpoints `POST /{offer_id}/evaluate` et `GET /{offer_id}/evaluation`)
  - `backend/tests/test_offer_evaluation.py` (new - tests unitaires du parsing, calcul de score, vérification quotas, et endpoints)
  - `frontend/src/lib/api.ts` (méthodes `evaluate` et `getEvaluation` dans `jobOffersApi`)
  - `frontend/src/types/jobOffer.ts` (new - types `OfferEvaluation`, `BlocA`, `BlocB`, `BlocG`)
  - `frontend/src/app/offers/page.tsx` (affichage du badge de score sur les cartes et lien vers la fiche détaillée)
  - `frontend/src/app/offers/[id]/page.tsx` (new - page de consultation détaillée du score, des Blocs A-G et actions rapides)
- **Files NOT touched**:
  - Services de crawl, normalisation, et pipeline de lettre de motivation existants.
- **Symbols replaced**: none.
- **Symbols extended**:
  - `JobOffer` et `JobOfferResponse` dans `backend/app/models.py` (`pipeline_stage`, `evaluation_score`).
  - `jobOffersApi` dans `frontend/src/lib/api.ts`.

## Definition of Done
- [x] Build passes: `python3 -m py_compile backend/app/models.py backend/app/services/evaluation/evaluator.py backend/app/routers/job_offers.py`
- [x] Frontend build passes: `npm --prefix frontend run build` (0 errors, `/offers/[id]` dynamic route generated)
- [x] Tests pass: `.venv/bin/pytest tests/test_offer_evaluation.py -v` (10 passed, 0 failures)
- [x] No dead code: n/a — aucun symbole supprimé ou rendu orphelin
- [x] Type check: zéro erreur TypeScript sur `frontend/src/app/offers/[id]/page.tsx` et `frontend/src/lib/api.ts`
- [x] Manual check: la route `/offers/[id]` affiche le score global (1.0-5.0), les blocs A, B et G, les exigences avec citations verbatim de l'offre, et permet d'évaluer ou postuler directement.

## Steps
- [x] Step 1: Dans `backend/app/models.py`, définir les modèles `RequirementMatch`, `MissingRequirement`, `BlocA`, `BlocB`, `BlocG`, `OfferEvaluation`, et étendre `JobOffer` / `JobOfferResponse` avec `pipeline_stage: Optional[str] = "discovered"` et `evaluation_score: Optional[float] = None`.
- [x] Step 2: Implémenter le service d'évaluation Two-Pass dans `backend/app/services/evaluation/evaluator.py` :
  - Pass 1 : analyse de l'offre (exigences pondérées `critical`, `high`, `meaningful`, archétype, détection ghost job Bloc G).
  - Pass 2 : matching avec `CandidateProfile` et `CandidatePreferences` (drapeaux rouges Bloc A, citations verbatim Bloc B, calcul score 1.0-5.0).
  - Enregistrement dans la collection `offer_evaluations`, intégration avec `require_user_quota()` et `record_api_usage()`.
- [x] Step 3: Dans `backend/app/routers/job_offers.py`, implémenter :
  - `POST /{offer_id}/evaluate` : déclenche l'évaluation Two-Pass pour l'utilisateur connecté.
  - `GET /{offer_id}/evaluation` : récupère l'évaluation détaillée associée au couple `(offer_id, user_id)`.
- [x] Step 4: Écrire les tests dans `backend/tests/test_offer_evaluation.py` (mocks LLM, vérification des blocs A-G, enforcement du quota, et endpoints).
- [x] Step 5: Dans le frontend :
  - Définir les types dans `frontend/src/types/jobOffer.ts`.
  - Étendre `jobOffersApi` dans `frontend/src/lib/api.ts`.
  - Ajouter les badges de score et liens de consultation dans `frontend/src/app/offers/page.tsx`.
  - Créer la page de consultation détaillée `frontend/src/app/offers/[id]/page.tsx` avec badges de score, onglets/sections des Blocs A-G, citations verbatim et actions rapides.
- [x] Step 6 (teardown): Validation backend (`py_compile` + `pytest`), build frontend (`npm run build`), mise à jour du journal d'exécution et de `DAILY_LOG`.

## Code Review
- Dead code removed: yes (no dead code introduced)
- Build status: pass (Next.js 15 build ok, pytest 10/10 passed)
- Type errors: none (strict TypeScript typing in frontend, Pydantic models in backend)
- Unintended side effects: none (existing job offers listing preserved with optional score badge)
- Security surface touched: no (standard auth-protected endpoints, user_id isolation)
- Verdict: PASS

## Execution Log
- Step 1 completed: Defined `RequirementMatch`, `MissingRequirement`, `BlocA`, `BlocB`, `BlocG`, `OfferEvaluation`, `OfferEvaluationResponse`, and added `pipeline_stage` & `evaluation_score` to `JobOfferCreate` and `JobOfferResponse` in `backend/app/models.py`. Verified with `python3 -m py_compile backend/app/models.py`.
- Step 2 completed: Implemented `backend/app/services/evaluation/evaluator.py` (Two-Pass protocol, Bloc A/B/G, verbatim quote extraction, score calculation, quota enforcement, and api_usage logging). Verified with `python3 -m py_compile backend/app/services/evaluation/evaluator.py`.
- Step 3 completed: Implemented `POST /job-offers/{offer_id}/evaluate` and `GET /job-offers/{offer_id}/evaluation` in `backend/app/routers/job_offers.py`.
- Step 4 completed: Wrote and passed 10 unit and endpoint tests in `backend/tests/test_offer_evaluation.py` (testing JSON parsing, score calculation with bounds and red flags, Two-Pass LLM mocks, quota 429 enforcement, and FastAPI endpoints).
- Step 5 completed: Defined frontend types in `frontend/src/types/jobOffer.ts`, updated `jobOffersApi` in `frontend/src/lib/api.ts`, enriched cards in `frontend/src/app/offers/page.tsx` with score badges and links, created detailed view in `frontend/src/app/offers/[id]/page.tsx`.
- Step 6 completed: Next.js production build (`npm --prefix frontend run build`) verified clean, 24/24 backend tests passing with 0 failures.

## Notes
- Score calculation formula:
  - Score de départ = 5.0
  - Red flag éliminatoire (geo-mismatch sévère, visa refusé, ghost job confirmé) -> Score plafonné à 1.5
  - Exigence `critical` manquante -> -1.0 par exigence
  - Exigence `high` manquante -> -0.5 par exigence
  - Exigence `meaningful` manquante -> -0.2 par exigence
  - Borne finale : min 1.0, max 5.0
