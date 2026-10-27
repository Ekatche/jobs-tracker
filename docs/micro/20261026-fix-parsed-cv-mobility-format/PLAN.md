---
task: Fix parsed CV mobility formatting in cv_parser.py and resumes.py
description: Aplatir contact.mobility (dict/list) en texte propre ' · ' dans _clean_parsed_cv (cv_parser.py) et assainir les chaînes dict résiduelles dans _build_candidate (resumes.py)
status: done
created: 2026-10-26
---

# Fix Parsed CV Mobility Formatting

## Context
- Existing code checked:
  - `backend/app/services/cv_parser.py:140-143` : `str(v).strip()` convertit les dictionnaires et listes renvoyés par le LLM pour `contact.mobility` en représentation textuelle Python (ex: `"{'permis': ['B (véhiculé)'], 'location': '<ville>'}"`).
  - Base de production vérifiée sur le VPS : le profil `6adf8e9b5a3ec3502417598c` contient exactement cette forme dans `mobility`.
  - `backend/app/routers/resumes.py:85` : `_build_candidate` applique `_clean_text` qui conserve telle quelle cette chaîne avec accolades Python.
- Fresh info looked up: n/a
- Git status checked: clean on Surgical Scope files (`cv_parser.py`, `resumes.py`).

## Simpler Alternative Considered
- Modifier manuellement le profil en base sans modifier le code : rejeté, tout futur parsing de CV par le LLM reproduirait la même chaîne brute.
- Corriger uniquement au moment du rendu : insuffisant, la base conserverait des données malformées. La solution combine l'aplatissement à l'ingestion (`cv_parser.py`) et la rétro-compatibilité au rendu (`resumes.py`).

## Surgical Scope
- **Files touched**:
  - `backend/app/services/cv_parser.py`
  - `backend/app/routers/resumes.py`
  - `backend/tests/test_resumes_api.py`
- **Files NOT touched**:
  - `backend/app/templates/cv/_macros.html`
  - `backend/app/services/cv_templates.py`
  - `backend/app/services/cv_tailor.py`
- **Symbols replaced**: none
- **Symbols extended**:
  - `_clean_parsed_cv` in `backend/app/services/cv_parser.py` (aplatissement des structures imbriquées dans `contact` via `_flatten_contact_value`)
  - `_build_candidate` in `backend/app/routers/resumes.py` (décodage défensif des chaînes dict existantes via `_clean_mobility`)

## Definition of Done
- [x] Build passes: `cd backend && uv run python -m py_compile app/services/cv_parser.py app/routers/resumes.py`
- [x] Tests pass: `cd backend && uv run pytest tests/test_resumes_api.py -v`
- [x] Full suite passes: `cd backend && uv run pytest tests` (1418 passed)
- [x] No dead code: n/a — aucun symbole remplacé
- [x] Deterministic check: `cd backend && uv run python -c "from app.routers.resumes import _clean_mobility; res = _clean_mobility(\"{'permis': ['B (véhiculé)'], 'location': 'Lyon'}\"); assert res == 'Permis B (véhiculé) · Lyon', f'Got: {res}'"`
- [x] Deployment: 495c09a sur `sentinel-vps` (`docker compose -f docker-compose.prod.yml up -d --build backend`), `/docs` 200, ping MongoDB `ok` depuis le backend

## Steps
- [x] Step 1: Ajouter la fonction d'aplatissement des champs de contact (`_flatten_contact_value`) dans `backend/app/services/cv_parser.py` pour transformer dicts et listes en chaînes jointes par ` · `.
- [x] Step 2: Ajouter le helper `_clean_mobility(value)` dans `backend/app/routers/resumes.py` pour désérialiser en toute sécurité les représentations textuelles Python existantes (`ast.literal_eval` sécurisé) et retourner une chaîne lisible.
- [x] Step 3: Écrire les tests unitaires couvrant l'aplatissement à l'ingestion et la désérialisation de secours dans `backend/tests/test_resumes_api.py`.
- [x] Step 4 (teardown): Vérifier la suite complète de tests backend.
- [x] Step 5: Déployer sur le VPS `sentinel-vps`.

## Code Review
- Dead code removed: no
- Build status: passed
- Type errors: none
- Unintended side effects: none
- Security surface touched: `ast.literal_eval` sur une chaîne issue du profil, seulement si elle commence par `{`/`[` et finit par `}`/`]` ; `ValueError`, `TypeError`, `SyntaxError`, `MemoryError` et `RecursionError` retombent sur le texte brut. Pas d'`eval()`.
- Verdict: ready

## Execution Log
- 2026-10-26T22:45Z | antigravity | step 1 | started
- 2026-10-26T22:46Z | antigravity | step 1 | done | `_flatten_contact_value` implemented in `cv_parser.py` and verified exit 0
- 2026-10-26T22:46Z | antigravity | step 2 | started
- 2026-10-26T22:48Z | antigravity | step 2 | done | `_clean_mobility` implemented in `resumes.py` and deterministic check passed
- 2026-10-26T22:48Z | antigravity | step 3 | started
- 2026-10-26T22:49Z | antigravity | step 3 | done | 3 new unit tests added in `tests/test_resumes_api.py` (28/28 passed)
- 2026-10-26T22:49Z | antigravity | step 4 | started
- 2026-10-26T22:49Z | antigravity | step 4 | done | Full CV suite passed: 76 passed, 0 failed in 12.48s
- 2026-10-26T23:15Z | claude | review | done | « Permis » préfixé quand la clé du dict le porte ; `_clean_mobility` réutilise `_flatten_contact_value` au lieu d'un second aplatissement ; tests anonymisés ; `uv run pytest tests` = 1418 passed
- 2026-10-26T23:21Z | claude | step 5 | started | commit 495c09a poussé, `git pull` sur le VPS
- 2026-10-26T23:22Z | claude | step 5 | incident | `docker compose` lancé sans `-f docker-compose.prod.yml` : backend et mongodb arrêtés, `jobtracker-mongodb` détaché de `job-tracker_app-network` ; relance prod OK mais `mongodb` non résolu depuis le backend
- 2026-10-27T06:04Z | claude | step 5 | done | réseau rétabli par l'utilisateur (recréation de mongodb via le compose prod) ; résolution `mongodb` OK depuis backend et airflow, ping `ok`, endpoints DB en 200

## Notes
- Un dict `{'permis': ['B']}` donnait « B » seul, illisible pour un recruteur : la clé `permis`/`licen…` préfixe désormais « Permis » sauf si la valeur le contient déjà.
- Les chaînes repr déjà stockées en base restent brutes : le CV rendu les lit correctement via `_clean_mobility`, mais le champ mobilité du frontend les affiche telles quelles. Script de réparation des profils proposé, non exécuté (décision utilisateur).
