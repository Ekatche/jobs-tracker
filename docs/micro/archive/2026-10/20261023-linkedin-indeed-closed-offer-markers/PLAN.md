---
task: Détecter les offres LinkedIn/Indeed closes dans le cron de vérification (archivage)
description: verify_job_offers cron closed offer detection — CLOSED_TEXT_PATTERNS regex for LinkedIn FR "Les candidatures ne sont plus acceptées" (figcaption closed-job__flavor--closed), Indeed "Cette offre a expiré sur Indeed" locked by test (already matched by offre a expiré pattern), is_redirected_to_generic_listing detects LinkedIn trk=expired_jd_redirect query; soft-delete pipeline_stage expired; Indeed blocked by Cloudflare 401 + headless networkidle timeout (limitation); pytest test_verify_job_offers
status: done
created: 2026-10-23
---

# Détecter les offres LinkedIn/Indeed closes dans le cron de vérification

## Context
- Existing code checked: `backend/app/tasks/verify_job_offers.py` (DAG `airflow/dags/verify_job_offers_dag.py`, quotidien 07:00 UTC, `limit=200`, `dry_run=False`). Clôture confirmée => soft-delete `is_deleted=True`, `pipeline_stage="expired"`, `deletion_reason`. Détection : 404/410, JSON-LD `validThrough`, redirection vers listing (`is_redirected_to_generic_listing`), regex `CLOSED_TEXT_PATTERNS` sur texte visible (HTTP puis headless Crawl4AI). Plan antérieur : `archive/2026-09/20260912-verify-active-job-offers` (logique 3 états, ne jamais supprimer sur erreur transitoire).
- Fresh info looked up (sondes réelles, 2026-10-23) :
  - LinkedIn offre close encore visible (`fr.linkedin.com/jobs/view/4299000013/`, HTTP 200) : `<figcaption class="closed-job__flavor--closed">Les candidatures ne sont plus acceptées</figcaption>`, espaces normaux. `detect_closure_in_text` renvoie `None` => offre gardée active.
  - LinkedIn offre purgée (ex. `jobs/view/4250000000`) : redirection 200 vers `.../jobs/<slug>-jobs?trk=expired_jd_redirect`. Non détecté (le chemin ne finit pas par `/jobs`) => raison `http_200_ok`, offre gardée active. 5 sondes sur 14 dans ce cas.
  - Indeed : `"Cette offre a expiré sur Indeed"` est déjà capté par le motif 1 (`offre ... a expiré`). Mais `fr.indeed.com/viewjob` renvoie 401 Cloudflare (`Authenticating... Redirecting to login...`) en HTTP, et le headless timeout à 60 s (`networkidle`) => statut `unknown`, jamais archivé. Le texte n'est jamais atteint.
- Git status checked: seuls `docs/micro/*` modifiés par d'autres sessions (INDEX.md, archive, 2 plans non suivis). Rien dans le périmètre code. INDEX.md reçoit un ajout append-only.

## Simpler Alternative Considered
Ajouter seulement le motif texte LinkedIn. Rejeté partiellement : les offres LinkedIn purgées ne montrent plus ce texte (redirection `expired_jd_redirect`), elles resteraient actives. Le check de query string est une ligne dans une fonction existante, signal non ambigu (« expired job description redirect »). Contourner le blocage Cloudflare d'Indeed : hors périmètre (anti-bot), signalé en Notes.

## Surgical Scope
- **Files touched**: `backend/app/tasks/verify_job_offers.py`, `backend/tests/test_verify_job_offers.py`
- **Files NOT touched**: tout le reste (DAG, `clean_job_offers.py`, logique de soft-delete, headless)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep): `CLOSED_TEXT_PATTERNS` (+1 motif), `is_redirected_to_generic_listing` (+1 condition), `test_detect_closure_in_text_real_world_platform_variants` (+2 cas), `test_is_redirected_to_generic_listing` (+1 cas)

## Definition of Done
- [ ] Build passes: `cd backend && uv run python -m py_compile app/tasks/verify_job_offers.py`
- [ ] Tests pass: `cd backend && uv run pytest tests/test_verify_job_offers.py -q` (38 avant, tous verts après)
- [ ] LinkedIn FR détecté : `cd backend && uv run python -c "from app.tasks.verify_job_offers import detect_closure_in_text as d; assert d('Les candidatures ne sont plus acceptées')"` exit 0
- [ ] Indeed détecté : `cd backend && uv run python -c "from app.tasks.verify_job_offers import detect_closure_in_text as d; assert d('Cette offre a expiré sur Indeed')"` exit 0
- [ ] Redirection LinkedIn détectée : `cd backend && uv run python -c "from app.tasks.verify_job_offers import is_redirected_to_generic_listing as r; assert r('https://fr.linkedin.com/jobs/view/4250000000/', 'https://www.linkedin.com/jobs/web-content-specialist-jobs?trk=expired_jd_redirect')"` exit 0
- [ ] Pas de faux positif : cas actifs existants de `test_detect_closure_in_text_no_false_positive_on_active_listing` et le cas « même offre `?ref=tracker` » restent verts (couvert par la commande pytest)
- [ ] No dead code: n/a — aucun symbole remplacé
- [ ] Type check: n/a — pas de type checker configuré pour backend
- [ ] Manual check: sonde réelle `check_url_http_fast('https://fr.linkedin.com/jobs/view/4299000013/')` renvoie `status: closed` (si LinkedIn ne répond pas 429)

## Steps
- [x] Step 1: Tests d'abord — ajouter `"Les candidatures ne sont plus acceptées"` et `"Cette offre a expiré sur Indeed"` au parametrize `test_detect_closure_in_text_real_world_platform_variants`, et un cas `trk=expired_jd_redirect` (+ un cas `trk=` autre valeur => False) dans `test_is_redirected_to_generic_listing`. Lancer pytest : le cas LinkedIn texte et le cas redirection doivent échouer (rouge), le cas Indeed passer.
- [x] Step 2: Ajouter à `CLOSED_TEXT_PATTERNS` le motif `r"candidatures ne sont plus acceptées"` (commentaire : bandeau LinkedIn FR).
- [x] Step 3: Dans `is_redirected_to_generic_listing`, retourner `True` si `"expired_jd_redirect"` figure dans `parse_qs(final_parsed.query).get("trk", [])` (redirection LinkedIn d'une offre purgée).
- [x] Step 4: Relancer pytest (vert) + les 3 commandes `python -c` du DoD + sonde manuelle LinkedIn.
- [x] Step 5 (teardown): aucun symbole remplacé ; vérifier `git diff --stat` limité aux 2 fichiers du Surgical Scope.

## Code Review
- Dead code removed: n/a — aucun symbole remplacé, seulement étendus
- Build status: pass (`py_compile` exit 0, pytest 40 passed)
- Type errors: none (pas de type checker backend ; diagnostic IDE `parse_qs` transitoire, résolu par l'import)
- Unintended side effects: none — le check `trk=expired_jd_redirect` s'applique aussi au chemin headless (`js_spa_redirected_to_listing`), voulu ; 3 offres LinkedIn actives réelles restent `valid` ; `trk=public_jobs_topcard` reste `False` (test)
- Security surface touched: no (regex + lecture de query string, aucun auth/secret/injection/migration)
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-23T18:12Z | claude-code | preflight | baseline | compile=0, pytest 38 passed, linkedin=1, indeed=0, redirect=1
- 2026-10-23T18:12Z | claude-code | step 1 | started
- 2026-10-23T18:13Z | claude-code | step 1 | done | pytest 38 passed, 2 failed (rouge attendu : cas LinkedIn texte + test_is_redirected_to_generic_listing ; cas Indeed vert)
- 2026-10-23T18:13Z | claude-code | step 2 | started
- 2026-10-23T18:13Z | claude-code | step 2 | done | assert LinkedIn exit 0 ; pytest 39 passed, 1 failed (redirection, step 3)
- 2026-10-23T18:13Z | claude-code | step 3 | started
- 2026-10-23T18:13Z | claude-code | step 3 | done | assert redirection exit 0 ; pytest 40 passed
- 2026-10-23T18:14Z | claude-code | step 4 | started
- 2026-10-23T18:14Z | claude-code | step 4 | done | compile=0, pytest 40 passed, linkedin=0, indeed=0, redirect=0 ; sonde réelle 4299000013 closed static_closed_text, 4250000000 closed redirected_to_generic_listing ; 3 offres actives (4446387035, 4440458716, 4478676988) valid http_200_ok
- 2026-10-23T18:14Z | claude-code | step 5 | started
- 2026-10-23T18:14Z | claude-code | step 5 | done | git diff --stat : 2 fichiers (verify_job_offers.py +7/-1, test_verify_job_offers.py +19), aucun symbole remplacé, 0 orphelin
- 2026-10-23T18:14Z | claude-code | close-out | done | compile=0, pytest 40 passed, linkedin=0, indeed=0, redirect=0 ; diff relu ligne à ligne

## Notes
- Preflight 2026-10-23 : conventions lues = `CLAUDE.md` racine (règles de tests : tests_for via code-review-graph, logique de détection d'offres closes = test à forte valeur). `tests_for` confirme `backend/tests/test_verify_job_offers.py`. Hors périmètre, modifiés par une autre session : `backend/app/routers/interview_prep.py`, `backend/tests/test_interview_prep_api.py` (non touchés).
- Baseline DoD : compile exit 0 ; pytest 38 passed ; assert LinkedIn exit 1 ; assert Indeed exit 0 ; assert redirection exit 1.
- **Indeed reste non détectable par ce cron** : 401 Cloudflare en HTTP, timeout headless => `unknown` (aucune suppression, comportement sûr mais aucune détection). Le motif texte est verrouillé par test pour le jour où la page est atteinte. Piste séparée, hors micro : sortir les offres Indeed du check headless (gain 60 s/offre), ou s'appuyer sur `cleanup_old_offers(days=40)` dans `clean_job_offers.py`.
- Correction (post-close) : `cleanup_old_offers` n'est PAS actif — le DAG `clean_job_offers` passe `enable_old_offers_cleanup=False`. Aucune offre Indeed n'est archivée automatiquement aujourd'hui. Doc mise à jour : `docs/JOB_INGESTION_AND_NORMALIZATION.md` (section liveness + limite Indeed), `docs/SYSTEM_ARCHITECTURE.md` (horaires réels 0 7 / 0 6 et description du nettoyage).
- LinkedIn renvoie aussi 429 sous rafale : déjà traité comme non-clôture (pas de suppression).
- Décision utilisateur 2026-10-23 : la purge par âge `cleanup_old_offers` reste désactivée (critère de date seul jugé pas assez robuste, et `delete_many` physique). La piste « s'appuyer sur `cleanup_old_offers` » ci-dessus est écartée : archivage uniquement sur signal de clôture réel.
