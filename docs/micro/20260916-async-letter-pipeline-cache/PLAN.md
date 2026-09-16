---
task: Rendre le pipeline cover_letter_crew asynchrone (acompletion, asyncio.gather) et ajouter un cache TTL pour la recherche d'entreprise
status: planned
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[x]` marker, Execution Log format, or evidence rule.

# Optimisation Async et Cache Entreprise

## Context
- Existing code checked: `backend/job_trackers/src/job_trackers/cover_letter_crew.py` utilise `litellm.completion` et s'exécute séquentiellement. `backend/app/routers/applications.py` encapsule cela dans `asyncio.to_thread`.
- Fresh info looked up: `litellm.acompletion` a la même signature. `AsyncTavilyClient` existe dans le SDK `tavily-python`. 
- Git status checked: clean, basé sur `fix/profile-multi-sources` fraîchement mergé dans `main` (seul un PLAN.md était modifié).

## Simpler Alternative Considered
- Conserver `asyncio.to_thread` global et utiliser `ThreadPoolExecutor` dans `run_letter_pipeline_sync`. Écarté car migrer vers de l'async natif (`acompletion`) est plus performant et idiomatique avec FastAPI/Motor.

## Surgical Scope
- **Files touched**: 
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/app/routers/applications.py`
  - `backend/tests/test_cover_letter_crew.py`
- **Files NOT touched**: All others
- **Symbols replaced**: `run_letter_pipeline_sync`, `_call_analyst`, `_search_company_web`, `_call_company_researcher`, `_call_writer`, `_call_critic`, `_call_reviser` (tous deviennent `async def`).
- **Symbols extended**: `COMPANY_CACHE` (nouveau dictionnaire mémoire avec TTL).

## Definition of Done
- [x] Build passes: `uv run ruff check backend/job_trackers/src/job_trackers/cover_letter_crew.py backend/app/routers/applications.py`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cover_letter_crew.py tests/test_applications.py`
- [x] No dead code: Les versions synchrones ont bien été remplacées par les versions `async def`.
- [x] Type check: `cd backend && uv run mypy backend/job_trackers/src/job_trackers/cover_letter_crew.py`
- [x] Manual check: n/a

## Steps
- [x] Step 1: Ajouter un cache mémoire simple `COMPANY_CACHE = {}` dans `cover_letter_crew.py` avec une logique TTL (ex: 7 jours) dans une nouvelle fonction asynchrone `_get_cached_or_research_company`.
- [x] Step 2: Convertir toutes les méthodes `_call_*` en `async def` et remplacer `completion` par `await acompletion`.
- [x] Step 3: Remplacer `TavilyClient` par `AsyncTavilyClient` dans `_search_company_web`.
- [x] Step 4: Renommer `run_letter_pipeline_sync` en `run_letter_pipeline_async` et utiliser `await asyncio.gather` pour exécuter l'analyste et le chercheur d'entreprise en parallèle.
- [x] Step 5: Mettre à jour `backend/app/routers/applications.py` pour appeler directement `await run_letter_pipeline_async` au lieu de `asyncio.to_thread(...)`.
- [x] Step 6: Mettre à jour `tests/test_cover_letter_crew.py` pour utiliser `pytest.mark.asyncio` et `await`.

## Code Review
- Dead code removed: yes (versions synchrones remplacées)
- Build status: pass (ruff 0 warnings)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-16 20:13 C16 (non commité) — feat(cover-letter): pipeline 100% async et cache mémoire TTL 7 jours pour la recherche web

## Notes
