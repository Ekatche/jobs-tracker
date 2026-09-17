---
task: Stabiliser la pagination des offres, enrichir les filtres (favoris, statuts, contrats) et identifier les nouvelles offres
status: done
created: 2026-09-17
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Stabiliser la pagination des offres, enrichir les filtres et identifier les nouvelles offres

## Context
- Existing code checked:
  - `backend/app/routers/job_offers.py`:
    - `get_job_offers` et `get_job_offers_count` ont une divergence de formule `dedup_key` (le count n'utilisait pas `$unique_key`).
    - Le pipeline MongoDB `$sort` manquait d'un tiebreaker déterministe (`_id: -1`), causant des permutations d'offres et doublons inter-pages lors de timestamps `created_at` identiques.
    - Les filtres supportés étaient limités (uniquement `only_saved`, `keywords`, `location`, `company`, `min_score`).
  - `frontend/src/app/offers/page.tsx`:
    - La pagination rechargeait inutilement le comptage à chaque changement de page, et ne réinitialisait pas `currentPage` de manière cohérente sur les filtres.
    - Manque d'indicateurs visuels et de filtres rapides clairs pour les favoris, les nouvelles offres (< 24h / < 48h), le type de contrat et le mode de travail.
  - `backend/app/models.py`:
    - `JobOfferResponse` nécessitait `created_at` et `updated_at` en `Optional[datetime]` pour prévenir les erreurs de validation sur d'anciens documents.
- Fresh info looked up: n/a
- Git status checked: clean/understood working tree.

## Simpler Alternative Considered
- Gérer les filtres uniquement en mémoire côté client : rejeté car la base contient de nombreuses offres paginées côté serveur (MongoDB `$skip`/`$limit`). Les filtres doivent s'appliquer sur l'ensemble de la base.

## Surgical Scope
- **Files touched**:
  - `backend/app/routers/job_offers.py`
  - `backend/app/models.py`
  - `backend/tests/test_job_offers_pipeline.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/app/offers/page.tsx`
- **Files NOT touched**:
  - All other routers, collector scripts, and unrelated components
- **Symbols replaced**:
  - `frontend/src/app/offers/page.tsx:Pagination` (remplacé par une pagination complète numérotée et stable)
- **Symbols extended**:
  - `get_job_offers` et `get_job_offers_count` in `backend/app/routers/job_offers.py` (ajout de `days_recent`, `contract_type`, `work_mode`, `interaction_status`, tiebreaker `_id: -1`, alignement `dedup_key`)
  - `JobOfferFilter` in `frontend/src/lib/api.ts` (ajout de `days_recent`, `contract_type`, `work_mode`, `interaction_status`)
  - `JobOfferResponse` in `backend/app/models.py` (champs datetime rendus optionnels)
  - Barre de filtres et `OfferCard` in `frontend/src/app/offers/page.tsx`

## Definition of Done
- [x] Build passes: `npm run build --prefix frontend` (exit 0)
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py` (exit 0, 11 passed)
- [x] No dead code: vérification que les anciens helpers inutilisés sont retirés
- [x] Type check: `npm run build --prefix frontend` (exit 0, types valides)
- [x] Manual check:
  - Le tri et la pagination restent stables sans offres manquantes ni doublons entre pages.
  - Le filtre Favoris affiche précisément les offres sauvegardées avec état visuel actif clair.
  - Les filtres rapides (Favoris, Nouvelles < 48h, Match IA) et filtres avancés (Contrat, Mode de travail) fonctionnent et réinitialisent la page à 1.
  - Les cartes d'offres affichent distinctement le badge "Nouveau" pour les offres récentes (< 24h / < 48h) ainsi que la date d'insertion en base.

## Steps
- [x] Step 1: Backend - Enrichir les paramètres de filtre et stabiliser l'agrégation dans `backend/app/routers/job_offers.py` :
  - Ajouter `days_recent: Optional[int]`, `contract_type: Optional[str]`, `work_mode: Optional[str]`, et `interaction_status: Optional[str]` dans `get_job_offers` et `get_job_offers_count`.
  - Harmoniser la formule `dedup_key` dans `count_pipeline` avec `get_job_offers`.
  - Ajouter le tiebreaker déterministe `{"created_at": -1, "_id": -1}` dans le tri avant et après groupement.
- [x] Step 2: Backend Models - Sécuriser `JobOfferResponse` dans `backend/app/models.py` (`created_at` et `updated_at` en `Optional[datetime] = None`).
- [x] Step 3: Backend Tests - Ajouter les tests dans `backend/tests/test_job_offers_pipeline.py` pour valider le filtrage par favoris/interaction, `days_recent`, `contract_type`, et la stabilité du tri déterministe.
- [x] Step 4: Frontend API - Mettre à jour `JobOfferFilter` et `jobOffersApi.getAll` / `getCount` dans `frontend/src/lib/api.ts` pour transmettre `days_recent`, `contract_type`, `work_mode`, `interaction_status`.
- [x] Step 5: Frontend UI - Refonte ergonomique des filtres, de la pagination et de l'identification des nouvelles offres dans `frontend/src/app/offers/page.tsx` :
  - Pilules de filtres rapides : "Toutes", "⭐ Favoris", "✨ Nouvelles (< 48h)", "⚡ Match IA (≥ 4.0)".
  - Panneau déroulant de filtres avancés : type de contrat (CDI, CDD, Freelance...), mode de travail (Télétravail, Hybride, Présentiel), localisation, entreprise, et période d'ajout.
  - Cartes d'offres : Badge bien visible "✨ Nouveau (< 24h)" ou "Nouveau (< 48h)" calculé à partir de `offer.created_at`, et affichage de la date d'ajout en base en bas de carte.
  - Pagination : Numérotation des pages avec boutons Précédent/Suivant, saut direct, clamping `currentPage <= totalPages`, et scroll fluide en haut de liste lors d'un changement de page.
- [x] Step 6: Teardown - Supprimer le code mort, exécuter `docker exec jobtracker-backend pytest tests/test_job_offers_pipeline.py` et `npm run build --prefix frontend`.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 09:44 | agy | step 1 | started
- 09:45 | agy | step 1 | done | tests pass (9 passed in 0.21s)
- 09:45 | agy | step 2 | started
- 09:45 | agy | step 2 | done | JobOfferResponse fields made optional, tests pass (9 passed in 0.17s)
- 09:46 | agy | step 3 | started
- 09:46 | agy | step 3 | done | tests pass (11 passed in 0.25s)
- 09:46 | agy | step 4 | started
- 09:46 | agy | step 4 | done | frontend build passed, TypeScript types valid
- 09:47 | agy | step 5 | started
- 09:48 | agy | step 5 | done | UI updated with quick pills, advanced filters, new badges, added date, and robust numbered pagination
- 09:49 | agy | step 6 | started
- 09:49 | agy | step 6 | done | 0 orphans, backend pytest (11 passed), frontend next build clean (exit 0)

## Notes
Baseline DoD tests passing.
All DoD commands passed in final close out.

