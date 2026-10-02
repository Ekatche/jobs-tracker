---
task: Conserver les offres à contrat non spécifié dans les filtres pour ne pas masquer d'opportunités
status: completed
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Conserver les offres à contrat non spécifié dans les filtres pour ne pas masquer d'opportunités

## Context
- Existing code checked:
  - 341 offres actives sur 465 ont `type_contrat = "Non spécifié"` dans la base car les ATS/jobboards ne renseignent pas toujours ce champ.
  - Le filtre strict `contract_type` dans `backend/app/routers/job_offers.py` excluait toute offre n'ayant pas explicitement la chaîne recherchée dans `type_contrat`.
  - Résultat : la recherche par profil (`CDI|CDD|Freelance`) masquait 358 offres réelles.
  - L'utilisateur a explicitement demandé : *"si non spécifié montre les quand même au lieu de les filtrer, le user va lui même les écarter"*.
- Fresh info looked up: n/a
- Git status checked: clean on expected files in scope.

## Simpler Alternative Considered
- Conserver le filtre strict et forcer l'utilisateur à choisir "Tous les contrats" : rejeté car l'utilisateur souhaite naviguer sur ses filtres cibles (CDI/CDD) sans perdre les opportunités non labellisées.

## Surgical Scope
- **Files touched**:
  - `backend/app/routers/job_offers.py`
  - `backend/tests/test_user_offer_interactions.py`
  - `frontend/src/app/offers/page.tsx`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `_build_contract_type_filter` in `backend/app/routers/job_offers.py`
  - `get_job_offers` and `get_job_offers_count` in `backend/app/routers/job_offers.py`
  - `currentFilters` and contract dropdown in `frontend/src/app/offers/page.tsx`

## Definition of Done
- [x] Backend tests pass: `docker exec jobtracker-backend pytest tests/test_user_offer_interactions.py` (17/17 passed)
- [x] Frontend build passes: `npm --prefix frontend run build` (compiled successfully)
- [x] Filter inclusion: Filtrer par "CDI" ou "Mes contrats ciblés" inclut bien les offres avec `type_contrat = "Non spécifié"`, `None` ou champ absent, tout en excluant les offres explicitement labellisées "Stage" ou "Alternance".
- [x] Direct Stage filter: Filtrer explicitement sur "Stage" ou "Alternance" continue de cibler exclusivement ces contrats.

## Steps
- [x] Step 1: Ajouter le helper `_build_contract_type_filter` dans `backend/app/routers/job_offers.py` et l'appliquer dans `get_job_offers` et `get_job_offers_count`.
- [x] Step 2: Ajouter des tests unitaires validant ce comportement dans `backend/tests/test_user_offer_interactions.py`.
- [x] Step 3: Mettre à jour `frontend/src/app/offers/page.tsx` pour s'assurer que les libellés et la transmission du filtre soient clairs et alignés.
- [x] Step 4: Exécuter la suite de tests et vérifier le build frontend Next.js.
- [x] Step 5: Consigner l'entrée dans `docs/micro/DAILY_LOG-2026-10-02.md`.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 19:42: Plan authored following user guidance to keep non-specified contracts in results.
- 2026-10-02 19:43: Implementation of `_build_contract_type_filter` in `job_offers.py` for both listing and count endpoints.
- 2026-10-02 19:43: Pytest suite executed successfully in Docker (17/17 passed).
- 2026-10-02 19:44: Next.js frontend production build verified (`next build` compiled successfully).

## Notes
- None.
