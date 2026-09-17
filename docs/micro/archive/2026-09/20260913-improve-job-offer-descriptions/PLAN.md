---
task: Améliorer la qualité et la structure des descriptions d'offres d'emploi générées par le crawler
status: completed
created: 2026-09-13
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Improve Job Offer Descriptions Quality and Structure

## Context
- Existing code checked:
  - `backend/job_crawler/crawler1.py`: `get_shared_crawl_config()` contains `instruction` for `LLMExtractionStrategy`. For `description`, the instruction was vague (*"un résumé clair, synthétique et informatif des missions principales, du contexte du poste et du profil recherché (2 à 5 phrases pertinentes)"*), leading to flat, unstructured paragraphs lacking actionable details.
  - `backend/app/tasks/job_offers_collectors.py`: receives `description` from the crawler and preserves it during MongoDB upsert.
  - `frontend/src/app/offers/page.tsx`: displays `offer.description` inside `<p className="... line-clamp-3 ...">`. Adding `whitespace-pre-line` and an expand/collapse toggle allows reading the rich structured text.
- Fresh info looked up: Best practices for job board LLM summaries (Context, Key Missions, Required Profile, Tech Stack, Perks/Work mode).
- Git status checked: workspace clean on previous micro-task.

## Simpler Alternative Considered
- Running an additional post-processing LLM pass in Airflow on each offer: rejected because it would double LLM latency and cost (~20 API calls per query). Formulating a structured extraction prompt directly in `Crawl4AI` achieves the same high quality with 0 extra latency and 0 additional LLM calls.

## Surgical Scope
- **Files touched**:
  - `backend/job_crawler/crawler1.py` (enrich LLM extraction instructions for structured Markdown descriptions with 5 distinct sections, increase `max_tokens` to 4000)
  - `backend/tests/test_job_offers_pipeline.py` (add test asserting structured description preservation)
  - `frontend/src/app/offers/page.tsx` (add `whitespace-pre-line` and expandable toggle to read full description)
  - `docs/micro/20260913-improve-job-offer-descriptions/PLAN.md`
  - `docs/micro/DAILY_LOG-2026-09-13.md`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `instruction` in `get_shared_crawl_config` in `crawler1.py`
  - `OfferCard` in `frontend/src/app/offers/page.tsx`

## Definition of Done
- [x] Build passes: `uv run --project backend python -c "from job_crawler.crawler1 import get_shared_crawl_config; print('OK')"`
- [x] Tests pass: `docker compose exec -T backend pytest tests/test_normalization.py tests/test_job_offers_pipeline.py` (16 passed in 3.60s)
- [x] No dead code: confirmed
- [x] Type check: n/a
- [x] Manual check: test extraction on a real job URL and verify that the resulting description contains clear sections (Contexte, Missions, Profil, Stack, Avantages).

## Steps
- [x] Step 1: Update extraction instructions in `backend/job_crawler/crawler1.py` to require structured 5-section Markdown descriptions with bullet points.
- [x] Step 2: Add test in `backend/tests/test_job_offers_pipeline.py` verifying structured descriptions are preserved without corruption.
- [x] Step 3: Enhance `OfferCard` in `frontend/src/app/offers/page.tsx` with `whitespace-pre-line` and a "Voir plus / Voir moins" toggle.
- [x] Step 4: Rebuild Docker backend container, execute tests inside container.
- [x] Step 5 (teardown): Live crawl verification on a real URL to confirm the new description structure.

## Code Review
- Dead code removed: yes
- Build status: passed (backend image rebuilt, container restarted)
- Type errors: none
- Unintended side effects: none (existing downstream tasks and models are fully compatible with string descriptions)
- Security surface touched: no
- Verdict: approved

## Execution Log
- [x] Step 1: Updated `instruction` in `backend/job_crawler/crawler1.py` detailing the 5 sections (Contexte & Enjeux, Missions principales, Profil recherché, Stack & Outils, Avantages & Modalités) and increased `max_tokens` to 4000.
- [x] Step 2: Added `test_structured_description_preservation` in `backend/tests/test_job_offers_pipeline.py`.
- [x] Step 3: Updated `OfferCard` in `frontend/src/app/offers/page.tsx` with `useState(false)` for expansion, `whitespace-pre-line` and dynamic toggle button.
- [x] Step 4: Built Docker backend image (`docker compose build backend`) and restarted container (`docker compose up -d backend`). Ran test suite inside Docker: 16 passed in 3.60s.
- [x] Step 5: Live crawl verification executed on `https://www.welcometothejungle.com/fr/companies/partoo/jobs/lead-developer-python-react-cdi-paris-m-f-d_paris`. Result obtained: perfect 5-section Markdown extraction with exact tech stack (FastAPI, Celery, React Typescript, Postgres) and clear bullet points.


## Notes
- Sections required in `description`:
  1. Contexte & Rôle (1-2 phrases)
  2. Missions principales (3-5 puces concrètes)
  3. Profil recherché (Expérience, diplôme, compétences indispensables)
  4. Stack & Environnement (Technologies, outils, organisation agile)
  5. Avantages & Modalités (Télétravail, salaire si mentionnés)
