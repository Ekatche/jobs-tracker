---
task: Restaurer la casse des sigles (FP&A, DRH, DAF…) dans les suggestions de rôles du profil
description: Suggestions de rôles « Suggestions basées sur votre profil » — backend/app/routers/cover_letters.py _canonicalize_roles applique str.title() aux variants role_aliases stockés en minuscules, ce qui donne « Fp&A », « Drh » ; nouveau helper _restore_title_acronyms (tokens avec &, liste de sigles d'intitulés de poste) appliqué aux variants et au retour du cache suggested_roles_cache ; tests test_cover_letters_api.py
status: done
created: 2026-10-24
---

# Casse des sigles dans les suggestions de rôles

## Context
- Existing code checked:
  - `normalize_role` et `match_taxonomy_role` (`backend/app/services/role_normalizer.py:41`, `:124`) stockent chaque variante en minuscules (`role_variant = role_clean.lower()`) ; le `canonical` garde la casse d'origine.
  - `_canonicalize_roles` (`backend/app/routers/cover_letters.py:293`) affiche les variantes liées avec `variant.strip().title()` (`:333`) : `"fp&a".title()` donne `"Fp&A"`, `"drh".title()` donne `"Drh"`.
  - `get_suggested_roles` (`:346`) renvoie les suggestions mises en cache sur le profil (`suggested_roles_cache`, `:376-377`) tant que l'empreinte du profil ne change pas : les caches déjà calculés gardent « Fp&A ».
  - `clean_job_title_syntax` (`backend/app/services/normalization.py:426`) ne touche pas à la casse.
  - Tests : `backend/tests/test_cover_letters_api.py:150` (cache complet) et `:189` (cache manquant), avec `role_aliases.find` mocké.
- Fresh info looked up: n/a — logique métier pure.
- Git status checked: `cover_letters.py` et `test_cover_letters_api.py` sans modification en cours.

## Simpler Alternative Considered
- Invalider tous les caches (version dans l'empreinte) au lieu de réparer au retour du cache. Rejeté : chaque profil relancerait l'appel LLM de suggestion et consommerait le quota `ROLE_SUGGESTION` de l'utilisateur, pour une correction purement typographique.
- Remplacer `.title()` par une casse de phrase (« Contrôleur de gestion FP&A »). Hors demande : l'utilisateur a validé la casse des sigles seulement. Proposé séparément.

## Surgical Scope
- **Files touched**: `backend/app/routers/cover_letters.py`, `backend/tests/test_cover_letters_api.py`
- **Files NOT touched**: tous les autres (dont `role_normalizer.py` : les variantes restent stockées en minuscules)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep): `_canonicalize_roles` (ligne `.title()` des variantes), `get_suggested_roles` (retour du cache)
- **Nouveaux symboles** : `TITLE_ACRONYMS`, `_restore_title_acronyms(title: str) -> str`

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.routers.cover_letters"` exit 0
- [x] Tests pass: `cd backend && uv run pytest tests/test_cover_letters_api.py -q` exit 0
- [x] Tests sans réseau : `cd backend && OPENAI_API_KEY=invalid GEMINI_API_KEY=invalid uv run pytest tests/test_cover_letters_api.py -q -k suggested_roles` exit 0
- [x] « Fp&A » corrigé : `cd backend && uv run python -c "from app.routers.cover_letters import _restore_title_acronyms as r; assert r('Contrôleur De Gestion Fp&A') == 'Contrôleur De Gestion FP&A'; assert r('Drh Adjoint') == 'DRH Adjoint'; assert r('Responsable Paie') == 'Responsable Paie'"` exit 0
- [x] No dead code: n/a — aucun symbole remplacé
- [x] Type check: n/a — pas de vérificateur de types configuré pour le backend
- [x] Lint : `uvx pyflakes backend/app/routers/cover_letters.py` sans nouvelle alerte par rapport à la baseline
- [ ] Manual check: après déploiement, l'utilisateur voit « FP&A » et non « Fp&A » dans « Suggestions basées sur votre profil » (observateur : l'utilisateur)

## Steps
- [x] Step 1: Ajouter dans `test_cover_letters_api.py` deux tests, d'abord rouges :
  - cache manquant : une variante `"contrôleur de gestion fp&a"` dans `role_aliases` ressort en `"Contrôleur De Gestion FP&A"` ;
  - cache complet contenant `"Contrôleur De Gestion Fp&A"` : la réponse renvoie `"Contrôleur De Gestion FP&A"`, sans appel LLM ni taxonomie.

  Vérification : `cd backend && uv run pytest tests/test_cover_letters_api.py -q -k suggested_roles` échoue sur ces deux tests seulement.
- [x] Step 2: Ajouter `TITLE_ACRONYMS` et `_restore_title_acronyms` dans `cover_letters.py` (un mot contenant `&` ou présent dans la liste passe en majuscules, le reste est inchangé). L'appliquer à la variante (`:333`) et aux suggestions renvoyées depuis le cache (`:377`).

  Vérification : `cd backend && uv run pytest tests/test_cover_letters_api.py -q` exit 0, et la commande « Fp&A corrigé » du Definition of Done exit 0.
- [x] Step 3 (teardown): aucun symbole remplacé, pas de scan d'orphelins. `uvx pyflakes backend/app/routers/cover_letters.py` comparé à la baseline.

## Code Review
- Dead code removed: n/a — aucun symbole remplacé
- Build status: pass
- Type errors: none (pas de vérificateur configuré)
- Unintended side effects: un rôle cible déjà enregistré par l'utilisateur sous la forme « …Fp&A » ne correspond plus à la suggestion « …FP&A » (comparaison `includes` sensible à la casse dans `TargetingPreferencesSection.tsx`) : la suggestion réapparaît comme cliquable. Il faut alors retirer l'ancienne forme à la main.
- Security surface touched: no — formatage d'un texte d'affichage, pas d'entrée utilisateur interprétée
- Verdict: ✅ DONE (le contrôle manuel après déploiement reste à faire par l'utilisateur)

## Execution Log
- 2026-10-24T20:54Z | claude-code | step 1 | started
- 2026-10-24T20:54Z | claude-code | step 1 | done | `pytest -k suggested_roles` : 2 failed (« Daf Adjoint » et « Fp&A » au lieu de « DAF Adjoint » et « FP&A »), 2 passed
- 2026-10-24T20:55Z | claude-code | step 2 | started
- 2026-10-24T20:55Z | claude-code | step 2 | done | `pytest tests/test_cover_letters_api.py -q` 10 passed ; commande « Fp&A corrigé » exit 0
- 2026-10-24T20:56Z | claude-code | step 3 | done | `uvx pyflakes` exit 0 sans sortie (baseline identique)
- 2026-10-24T20:56Z | claude-code | close | done | DoD : build exit 0, 10 passed, hors réseau 4 passed, Fp&A exit 0, pyflakes exit 0 ; diff relu (+37 -2 dans cover_letters.py, 2 tests ajoutés)

## Notes
- Conventions lues : `CLAUDE.md` racine (directives tests : contrats d'API et logique métier conservés).
- Baseline (Phase 3) : `uvx pyflakes app/routers/cover_letters.py` sans sortie ; `pytest tests/test_cover_letters_api.py -q` 8 passed ; import du routeur exit 0 (collecte des tests).
- Exécution approuvée par l'utilisateur le 2026-10-24 (« ok pour (a) »).
