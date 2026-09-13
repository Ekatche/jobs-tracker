---
task: Optimiser automatiquement les URLs LinkedIn et Indeed pour contourner les anti-bots et accélérer le scraping
status: completed
created: 2026-09-13
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Rewrite LinkedIn and Indeed URLs for Anti-Bot Bypass

## Context
- Existing code checked:
  - `backend/app/services/normalization.py`: contains normalizers (`normalize_company`, `extract_company_from_url`), but no URL optimization for crawling.
  - `backend/job_crawler/crawler1.py`: ingests raw URLs directly into `crawler.arun_many(urls=pending)`. Indeed desktop URLs (`/viewjob`) frequently hit 45s Cloudflare navigation timeouts, and LinkedIn standard URLs (`/jobs/view`) risk authwall redirects.
  - Empirical tests validated:
    - LinkedIn guest API (`https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<id>`) bypasses authwall, downloads in ~300ms, and yields 100% rich job postings.
    - Indeed mobile view (`https://fr.indeed.com/m/viewjob?jk=<id>`) bypasses Cloudflare desktop timeouts and renders immediately.
- Fresh info looked up: URL patterns for LinkedIn (`/jobs/view/(\d+)` or slug with ID) and Indeed (`[?&]jk=([a-zA-Z0-9]+)`).
- Git status checked: workspace clean on previous micro-task, ready for surgical addition.

## Simpler Alternative Considered
- Running full stealth browser with rotating proxies: expensive, heavy latency, unnecessary when lightweight endpoints exist for public job indexing.
- Manual regex in Airflow DAG: fragile, doesn't protect direct crawler calls or CLI usage. Normalizing at the crawler boundary ensures complete protection.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/normalization.py` (add `optimize_crawl_url`, `restore_canonical_job_url`)
  - `backend/job_crawler/crawler1.py` (map incoming URLs through `optimize_crawl_url` while preserving user-facing URL in extracted offers)
  - `backend/tests/test_normalization.py` (unit tests for `optimize_crawl_url` and `restore_canonical_job_url`)
  - `backend/tests/test_job_offers_pipeline.py` (integration test verifying crawler URL optimization and original URL preservation)
  - `docs/micro/20260913-rewrite-linkedin-indeed-urls/PLAN.md`
  - `docs/micro/DAILY_LOG-2026-09-13.md`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `optimize_crawl_url`, `restore_canonical_job_url` in `normalization.py` (new)
  - `crawl_and_extract_jobs_optimized` in `crawler1.py` (uses optimized URLs for crawling, restores canonical/original user-facing URLs for saved offers)

## Definition of Done
- [x] Build passes: `uv run --project backend python -c "from app.services.normalization import optimize_crawl_url, restore_canonical_job_url; print('OK')"`
- [x] Tests pass: `uv run --project backend pytest backend/tests/test_normalization.py backend/tests/test_job_offers_pipeline.py` (15/15 passed)
- [x] No dead code: confirmed
- [x] Type check: n/a
- [x] Manual check: verified with real URLs (LinkedIn `klanik-4463811288` and Indeed `40a89e89e93a1394`) crawled in 14s with 2/2 success and canonical user-facing URLs preserved.

## Steps
- [x] Step 1: Implement `optimize_crawl_url(url: Optional[str]) -> str` and `restore_canonical_job_url(url: Optional[str]) -> str` in `backend/app/services/normalization.py`.
- [x] Step 2: Add unit tests for `optimize_crawl_url` and `restore_canonical_job_url` in `backend/tests/test_normalization.py` covering standard and edge-case URLs for LinkedIn, Indeed, and other unimpacted job boards (WTTJ, Apec).
- [x] Step 3: Integrate `optimize_crawl_url` and `restore_canonical_job_url` in `backend/job_crawler/crawler1.py`:
  - Map URLs before `arun_many`.
  - Ensure extracted offers retain the original user-facing URL in `offer["url"]` and `offer["source_url"]`.
- [x] Step 4: Add pipeline unit test in `backend/tests/test_job_offers_pipeline.py` verifying that original user-facing URLs are preserved after crawl.
- [x] Step 5 (teardown): Rebuild Docker container, run test suite inside container (15/15 passed in 2.94s), verify 0 orphans and test with real live URLs.

## Code Review
- Dead code removed: yes
- Build status: pass (15/15 tests passed in local backend and container)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- [x] 20:30 Step 1: Implemented `optimize_crawl_url` and `restore_canonical_job_url` in `backend/app/services/normalization.py` for LinkedIn (`/jobs-guest/jobs/api/jobPosting/<id>`) and Indeed (`/m/viewjob?jk=<id>`).
- [x] 20:30 Step 2: Added `test_optimize_crawl_url` and `test_restore_canonical_job_url` in `backend/tests/test_normalization.py`. Passed 7/7.
- [x] 20:31 Step 3: Integrated `optimize_crawl_url` and canonical restoration in `backend/job_crawler/crawler1.py`. Offers now preserve original clickable URLs while crawling the fast/unblocked endpoints.
- [x] 20:32 Step 4: Added `test_crawler_preserves_user_facing_urls_with_optimization` in `backend/tests/test_job_offers_pipeline.py`. All 15 unit tests passed locally.
- [x] 20:33 Step 5: Rebuilt Docker backend image (`docker compose build backend`), restarted container (`docker compose up -d backend`), ran test suite inside container: 15/15 passed in 2.94s. Verified in real conditions with live LinkedIn and Indeed URLs: both extracted in 14s with user-facing URLs perfectly preserved.

## Notes
- `optimize_crawl_url` handles various LinkedIn URL styles (slugs, query parameters) and Indeed styles (`/viewjob`, `/rc/clk`).
- The candidate always receives a clickable browser URL (`/jobs/view/...` or original Indeed URL), not the internal guest endpoint.

