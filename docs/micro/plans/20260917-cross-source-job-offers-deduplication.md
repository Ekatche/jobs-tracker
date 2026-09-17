---
task: Déduplication sémantique cross-sources et fusion des offres multidiffusées
status: done
created: 2026-09-17
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Déduplication sémantique cross-sources et fusion des offres multidiffusées

## Context
- Existing code checked:
  - `backend/app/services/normalization.py` : `compute_unique_key()` concaténait l'URL brute (`{norm_comp}|{norm_pos}|{clean_url}`) si présente, créant des clés différentes pour la même offre diffusée sur WTTJ et LinkedIn.
  - `backend/app/tasks/job_offers_collectors.py` : `save_job_offers()` utilisait un simple `$set` sans réconciliation sémantique contre les offres déjà en base.
  - `backend/app/services/normalization.py` : `are_offers_duplicates()` et `merge_multidiffusion_offers()` existaient déjà pour la similarité et la fusion avec hiérarchie des sources (ATS 100 > WTTJ 80 > LinkedIn 50).
  - Base MongoDB : Doublons réels identifiés (Deloitte Lyon, Volvo Group, CS Group entre WTTJ/HelloWork et LinkedIn).
- Fresh info looked up: n/a
- Git status checked: Arbre fonctionnel et testé.

## Simpler Alternative Considered
- Dédupliquer uniquement par `unique_key` sans vérifier le matching sémantique en base : insuffisant car des offres historiques en base peuvent avoir une `unique_key` absente ou un format de titre légèrement différent.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/normalization.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/retroactive_dedup_job_offers.py`
  - `backend/tests/test_normalization.py`
  - `backend/tests/test_job_offers_pipeline.py`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `compute_unique_key` dans `backend/app/services/normalization.py` : clé canonique sémantique `{norm_comp}|{norm_pos}|{norm_loc}`
  - `merge_multidiffusion_offers` dans `backend/app/services/normalization.py` : préservation de `evaluation`, `user_interaction` et calcul canonique de `unique_key`
  - `save_offers_to_database` dans `backend/app/tasks/job_offers_collectors.py` : recherche des offres existantes par `unique_key`, `url`, `alternative_urls` ou `are_offers_duplicates`, puis fusion au lieu d'insertion de doublons
  - Tests unitaires dans `test_normalization.py` et `test_job_offers_pipeline.py`
- `backend/retroactive_dedup_job_offers.py` pour le nettoyage rétroactif en base.

## Definition of Done
- [x] Build passes: `docker exec jobtracker-backend pytest tests/test_normalization.py` (8/8 passés)
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_normalization.py tests/test_job_offers_pipeline.py` (20/20 passés)
- [x] No dead code: confirm 0 orphan symbols
- [x] Type check: `n/a`
- [x] Manual check: Déduplication rétroactive exécutée sur MongoDB : les 2 offres Deloitte Lyon ont été fusionnées en 1 seule offre avec l'URL WTTJ en primaire et l'URL LinkedIn dans `alternative_urls`, et le HTML résiduel nettoyé.

## Steps
- [x] Step 1: Adapter `compute_unique_key` dans `backend/app/services/normalization.py` pour produire une clé canonique indépendante de l'URL (`{norm_comp}|{norm_pos}|{norm_loc}`), et mettre à jour `test_compute_unique_key` dans `backend/tests/test_normalization.py`.
- [x] Step 2: Améliorer `merge_multidiffusion_offers` dans `backend/app/services/normalization.py` pour préserver `evaluation`, `user_interaction` et les identifiants existants sans régression.
- [x] Step 3: Dans `save_offers_to_database` (`backend/app/tasks/job_offers_collectors.py`), avant insertion, chercher les offres existantes par `unique_key`, `url`, `alternative_urls` ou correspondance sémantique (`are_offers_duplicates`), et fusionner les documents avec `merge_multidiffusion_offers` au lieu d'insérer des doublons.
- [x] Step 4: Écrire et exécuter un script de nettoyage rétroactif sur MongoDB pour fusionner les doublons cross-sources existants (dont le doublon Deloitte Lyon).
- [x] Step 5: Valider avec les tests unitaires pytest (`test_normalization.py` et `test_job_offers_pipeline.py`).
- [x] Step 6 (teardown): Vérifier qu'aucun doublon ne subsiste pour Deloitte Lyon dans MongoDB et vérifier le log d'exécution.

## Code Review
- Dead code removed: yes
- Build status: pass (20/20 tests)
- Type errors: none
- Unintended side effects: none (recherche rapide indexée par clé canonique + URL avec fallback sémantique par entreprise)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-17 10:00: Step 1 completed. `compute_unique_key` génère la clé canonique sémantique indépendante de l'URL (`{norm_comp}|{norm_pos}|{norm_loc}`). Tests passés dans `test_normalization.py` (8/8 passés).
- 2026-09-17 10:01: Step 2 completed. `merge_multidiffusion_offers` préserve `evaluation`, `user_interaction` et garantit la clé canonique.
- 2026-09-17 10:03: Step 3 completed. `save_offers_to_database` enrichi avec recherche cross-sources et fusion automatique. Test unitaire `test_save_offers_to_database_cross_source_dedup` ajouté et validé (12/12 passés dans `test_job_offers_pipeline.py`).
- 2026-09-17 10:04: Step 4 completed. Script `backend/retroactive_dedup_job_offers.py` exécuté dans le conteneur backend : 3 doublons fusionnés (Deloitte, Volvo Group, CS Group).
- 2026-09-17 10:04: Step 5 completed. Suite de tests complète validée dans le conteneur (`20 passed in 0.21s`).
- 2026-09-17 10:04: Step 6 completed. Vérification API et MongoDB : exactement 1 offre Deloitte Lyon retournée (`https://www.welcometothejungle.com/...` en URL principale, LinkedIn dans `alternative_urls`, HTML résiduel nettoyé).

## Notes
- 3 doublons cross-sources fusionnés en base : Deloitte (WTTJ + LinkedIn), Volvo Group (HelloWork + LinkedIn), CS Group (WTTJ + LinkedIn).
