---
task: Découper le travail non commité de fix/profile-multi-sources en plusieurs commits par sujet, merger sur main, pousser sur origin, reconstruire le docker local
status: planned
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Découpage multi-sujets + merge main + push + rebuild docker

## Context

- Branche actuelle : `fix/profile-multi-sources`. Remote : `origin` = `upstream` =
  `https://github.com/Ekatche/jobs-tracker.git`.
- Demande utilisateur (verbatim) : "merge sur main, reconstruit mon docker local
  et commit + push on remote", précisée ensuite par : inclure `fetch_urls.py` /
  `fetch_urls2.py` dans le commit, et "Plusieurs commits par sujet (Recommandé)"
  plutôt qu'un commit unique.
- État constaté : ~45 fichiers trackés modifiés + ~55 fichiers untracked
  (`git status --porcelain=v1 -uall` fait foi). Le travail couvre au moins 14
  sujets distincts (usage tracking, onboarding, cover letter, crawler, pipeline
  kanban, évaluation two-pass, profil multi-sources, CV parsing VLM,
  normalisation, UI, docker, docs).
- **Contrainte découverte** : plusieurs fichiers backend centraux
  (`backend/app/models.py`, `backend/app/routers/applications.py`,
  `backend/app/routers/cover_letters.py`) mélangent dans le **même diff non
  commité** des hunks appartenant à des sujets différents. Une séparation par
  fichier entier serait donc soit imprécise, soit franchement fausse pour ces
  3 fichiers. `backend/app/routers/job_offers.py`, `backend/app/routers/users.py`,
  `backend/app/routers/__init__.py`, `backend/main.py` ont été vérifiés
  **mono-sujet** (diff lu en entier) et n'ont pas besoin de split.
- Diffs complets déjà sauvegardés en analyse dans le scratchpad de session
  (non persistants) : `applications.diff`, `models.diff`, `job_offers.diff`,
  `users.diff`, `routers_init.diff`, `main.diff`, `rest1.diff`. Si perdus,
  refaire `git diff <fichier>` — le contenu ci-dessous en Surgical Scope
  contient déjà tout le nécessaire pour reconstruire les patches sans les
  rouvrir.
- Un seul patch a déjà été écrit sur disque avant l'interruption :
  `/private/tmp/claude-501/-Users-elielkatche-job-tracker/2b10eddc-24b3-4fbd-b287-4015c8d19b04/scratchpad/c1_models.patch`
  (hunk `ApiUsageAction`/`ApiUsageRecord`/`TierQuota`/`ActionQuotaUsage`/`UserQuotaSummary`).
  **Ce répertoire scratchpad est temporaire et peut avoir disparu** — le
  régénérer depuis le contenu exact donné à l'étape C1 ci-dessous si absent.

## Simpler Alternative Considered

Un unique commit global (plus simple, zéro risque de split cassé) a été
explicitement écarté par l'utilisateur au profit de "plusieurs commits par
sujet". Une séparation par hunk fin (`git add -p` ligne à ligne) sur
`applications.py` a aussi été écartée : les hunks pipeline/évaluation/usage-
tracking y sont trop imbriqués (un même hunk modifie parfois 2 sujets à la
fois, voir C5 ci-dessous) — le risque de casser une commande `git apply`
manuelle dépasse la valeur d'une pureté par sujet à 100 %. Compromis retenu :
split par hunk là où c'est propre (`models.py`, `cover_letters.py`), bundle
assumé et documenté là où ça ne l'est pas (`applications.py` → commit C5).

## Surgical Scope

- **Fichiers touchés** : la totalité du `git status` de la branche
  `fix/profile-multi-sources` (voir liste par commit ci-dessous, sections C1
  à C14). Aucun fichier hors de cette liste ne doit être ajouté.
- **Fichiers NOT touched** : aucun fichier du dépôt en dehors de l'arbre de
  travail actuel (pas de nouveau fichier créé hors de ceux déjà untracked
  listés par `git status`).
- **Symbols replaced** : aucun (uniquement des commits, pas de réécriture de
  code — le contenu final du répertoire après C1..C14 doit être bit-à-bit
  identique à l'état actuel du working tree avant de commencer).
- **Symbols extended** : aucun.

## Definition of Done

- [ ] `git status --porcelain=v1 -uall` vide après C1..C14 (plus rien à
      committer).
- [ ] `git diff main..fix/profile-multi-sources --stat` après C1..C14 est
      strictement identique (mêmes fichiers, mêmes +/-) au `git diff` capturé
      avant de commencer le split (aucune ligne perdue ni dupliquée par les
      opérations `git apply --cached`).
- [ ] Tests backend : `cd backend && uv run pytest` → tous verts (313+ tests
      avant cette session, ne doit pas régresser).
- [ ] Merge : `git checkout main && git merge --no-ff fix/profile-multi-sources`
      sans conflit.
- [ ] Push : `git push origin main` accepté par le remote.
- [ ] Docker : `docker compose build && docker compose up -d` (ou
      équivalent déjà en place dans `docker-compose.yml`) démarre sans erreur.

## Steps

Chaque étape Cn = un commit. Ordre à respecter strictement (les commits
partiels sur `models.py`/`applications.py`/`cover_letters.py` dépendent de
l'état laissé par le commit précédent sur ce même fichier — regénérer
`git diff <fichier>` avant chaque `git apply --cached` partiel, ne jamais
réutiliser un patch pré-calculé sur un état du fichier qui a changé).

**Méthode pour un fichier scindé (`models.py`, `applications.py` reçoit un
patch, `cover_letters.py`)** : construire un patch unifié minimal
(`diff --git a/<f> b/<f>` + `--- a/<f>` + `+++ b/<f>` + les seuls hunks du
sujet courant, texte exact recopié depuis `git diff <fichier>` au moment de
l'étape), puis `git apply --cached <patch>`. Vérifier avant de committer avec
`git diff --cached <fichier>` que seul le hunk voulu est staged.

- [x] **C1 — feat(usage-tracking): infrastructure API usage tracking et quotas**
  - Ajout entier : `backend/app/services/usage_tracker.py`,
    `backend/app/routers/usage.py`, `backend/tests/test_usage_tracker.py`,
    `backend/app/routers/__init__.py` (100% mono-sujet, vérifié),
    `backend/main.py` (100% mono-sujet, vérifié),
    `docs/micro/20260915-api-usage-tracking-and-quotas/PLAN.md`.
  - Patch partiel `backend/app/models.py` : hunk `@@ -28,6 +28,12 @@ class PyObjectId(str):`
    ajoutant `class UserTier(str, Enum): FREE/ADVANCED/PRO` (nécessaire car
    `UserQuotaSummary.tier: UserTier` en dépend) **+** le hunk final
    `@@ -405,3 +405,53 @@ class CoverLetter(BaseModel):` ajoutant
    `ApiUsageAction`, `ApiUsageRecord`, `TierQuota`, `ActionQuotaUsage`,
    `UserQuotaSummary` (contenu exact déjà dans `c1_models.patch`, à
    compléter avec le hunk UserTier ci-dessus si le fichier a disparu).
  - Ne PAS inclure ici les champs `tier`/`onboarding_completed` sur
    `UserModel`/`UserResponse` (→ C2).

- [x] **C2 — feat(users): tier utilisateur et flag onboarding**
  - Patch partiel `models.py` : les 2 hunks restants ajoutant
    `tier: UserTier = UserTier.FREE` + `onboarding_completed: Optional[bool] = False`
    sur `UserModel` et sur `UserResponse` (2 hunks proches, `@@ -36,6 +42,8 @@`
    et `@@ -81,6 +91,8 @@` dans le diff original — recalculer les offsets
    via un `git diff backend/app/models.py` frais après C1).
  - Ajout entier : `backend/app/routers/users.py` (100% mono-sujet : endpoint
    `POST /complete-onboarding`), `backend/tests/test_onboarding.py`,
    `frontend/src/app/onboarding/page.tsx`,
    `docs/micro/20260916-onboarding-wizard-page/PLAN.md`.

- [x] **C3 — feat(cover-letter): prompts optimisés + tracking usage tokens**
  - Ajout entier : `backend/app/llm/prompts/cover_letter/02_style.md`,
    `03_critique.md`, `04_revision.md`, `backend/app/llm/utils.py`,
    `backend/job_trackers/src/job_trackers/cover_letter_crew.py`,
    `backend/tests/test_cover_letter_crew.py`,
    `backend/tests/test_cover_letter_trigger.py`.
  - Suppression : `backend/job_trackers/src/job_trackers/config/letter_agents.yaml`,
    `backend/job_trackers/src/job_trackers/config/letter_tasks.yaml` (déjà
    `git rm`, statut `D` en staging — confirmer qu'ils restent staged).
  - Patch partiel `backend/app/routers/cover_letters.py` : les hunks
    `@@ -11,7 +11,7 @@` (import `ApiUsageAction`), `@@ -19,6 +19,7 @@`
    (import `usage_tracker`), `@@ -164,6 +165,8 @@` et `@@ -172,7 +175,20 @@`
    (quota + `record_api_usage` dans `import_cv_source`). **Ne pas inclure**
    le hunk `@@ -239,6 +255,28 @@` (endpoint préférences → C7).
  - `docs/micro/20260915-improve-cover-letter-prompt-career-ops/PLAN.md`.

- [x] **C4 — fix(llm): température des modèles de raisonnement**
  - Ajout entier : `backend/job_trackers/src/job_trackers/crew.py` (déjà
    audité cette session, cohérent avec `config/agents.yaml`/`config/tasks.yaml`).
  - `docs/micro/20260915-fix-reasoning-models-temperature/PLAN.md`.

- [x] **C5 — feat(pipeline): kanban, cadences de relance, résumé pipeline**
  - Ajout entier : `backend/app/routers/applications.py` — **bundle assumé** :
    ce fichier contient aussi les endpoints de déclenchement d'évaluation
    (`evaluate_application_offer`, `get_application_evaluation`) et les appels
    `require_user_quota`/`record_api_usage` de C1/C3, parce que
    `enrich_application_with_cadences(...)` est appelé dans le même hunk que
    `require_user_quota(...)` à plusieurs endroits (`create_application`,
    `update_application`) — pas de séparation propre possible sans risquer un
    état intermédiaire non fonctionnel. Mentionner ce bundle dans le message
    de commit.
  - Patch partiel `models.py` : hunk `ApplicationStatus.OFFER_RECEIVED` +
    `offer_id` sur `JobApplication*` + `days_since_application`/
    `follow_up_alert` + `PipelineSummaryResponse`.
  - Ajout entier : `backend/tests/test_applications.py`,
    `backend/tests/test_pipeline_kanban.py`,
    `frontend/src/components/applications/ApplicationCard.tsx`,
    `ApplicationDetails.tsx`, `StatusSelect.tsx`,
    `frontend/src/components/dashboard/NewApplicationModal.tsx`,
    `frontend/src/app/applications/page.tsx`, `frontend/src/app/pipeline/page.tsx`,
    `frontend/src/lib/api.ts`, `frontend/src/types/application.ts`.
  - `docs/micro/20260916-pipeline-kanban-offer-linking-cadences/PLAN.md`,
    `docs/micro/20260916-pipeline-kanban-state-machine/PLAN.md`.

- [x] **C6 — feat(evaluation): pipeline d'évaluation d'offre Two-Pass**
  - Ajout entier : `backend/app/routers/job_offers.py` (100% mono-sujet,
    vérifié), `backend/app/services/evaluation/__init__.py`,
    `backend/app/services/evaluation/evaluator.py`,
    `backend/tests/test_offer_evaluation.py`,
    `frontend/src/app/offers/[id]/page.tsx`, `frontend/src/app/offers/page.tsx`,
    `frontend/src/types/jobOffer.ts`.
  - Patch partiel `models.py` : hunk `JobOfferCreate`/`JobOfferResponse`
    `pipeline_stage`/`evaluation_score` + `JobOfferFilter.min_score` + le
    bloc `RequirementMatch`/`MissingRequirement`/`BlocA`/`BlocB`/`BlocG`/
    `OfferEvaluation`/`OfferEvaluationResponse`.
  - `docs/micro/20260916-offer-evaluation-two-pass/PLAN.md`,
    `docs/micro/20260916-fix-evaluator-candidate-profile-lookup/PLAN.md`,
    `docs/micro/20260916-improve-job-offers-readability-and-details-icon/PLAN.md`.

- [x] **C7 — feat(profile): sources multiples, préférences de ciblage, dédup projets**
  - Ajout entier : `backend/app/services/profile/collectors/website.py`,
    `backend/app/services/profile/collectors/github.py`,
    `backend/app/services/profile/merge.py`,
    `frontend/src/components/profile/CvDropzone.tsx`,
    `frontend/src/components/profile/TargetingPreferencesSection.tsx`,
    `frontend/src/app/profile/page.tsx`,
    `frontend/src/components/profile/CandidateProfileSection.tsx`,
    `backend/tests/test_candidate_preferences.py`,
    `backend/tests/test_profile_collectors.py`,
    `backend/tests/test_profile_merge.py`.
  - Patch partiel `models.py` : hunk import `model_validator` +
    `CandidateProject.repo`/`highlights` + `RemotePolicy`/`CandidatePreferences`
    (+ `CandidateProfile.preferences`) + `CandidateProfile.excluded_projects`.
  - Patch partiel `cover_letters.py` (reste du split C3) : hunk
    `@@ -239,6 +255,28 @@` (`update_candidate_preferences`).
  - `docs/micro/20260915-profile-targeting-preferences/PLAN.md`,
    `docs/micro/20260916-profile-bullet-points-and-project-dedup/PLAN.md`,
    `docs/micro/20260916-candidate-profile-dates-headline-projects/PLAN.md`,
    `docs/micro/20260916-profile-education-github-evaluator-match/PLAN.md`,
    `docs/micro/20260916-profile-scrollable-and-manual-crud/PLAN.md`.

- [x] **C8 — feat(cv-parser): extraction CV par VLM avec fallback texte**
  - Ajout entier : `backend/app/services/cv_parser.py` (VLM + `_usage`
    imbriqués dans les mêmes fonctions, non séparables),
    `backend/tests/test_cv_vlm_parser.py`.
  - `docs/micro/20260915-portfolio-deep-scraping-vlm-cv-ux/PLAN.md`.

- [x] **C9 — fix(crawler): robustesse extraction LLM en production**
  - Ajout entier : `backend/job_trackers/src/job_trackers/tools/custom_tool.py`,
    `backend/job_crawler/crawler1.py`, `backend/scripts/crawl_bakeoff.py`,
    `backend/fetch_urls.py`, `backend/fetch_urls2.py` (scripts scratch inclus
    sur demande explicite de l'utilisateur),
    `docs/micro/20260916-crawl-llm-bakeoff/` (tous les fichiers).

- [x] **C10 — feat(ingestion): normalisation ville/entreprise/domaine**
  - Ajout entier : `backend/app/services/normalization.py`,
    `backend/tests/test_normalization.py`, `docs/JOB_INGESTION_AND_NORMALIZATION.md`.

- [x] **C11 — feat(ui): sidebar, header, refonte landing RGPD**
  - Ajout entier : `frontend/src/components/layout/Header.tsx`,
    `frontend/src/app/page.tsx`.
  - `docs/micro/20260916-sidebar-modernization-and-in-kanban-scoring/PLAN.md`,
    `docs/micro/20260916-landing-monsuivijob-rgpd-redesign/PLAN.md`.

- [x] **C12 — chore(docker): montage volume frontend en local**
  - Ajout entier : `docker-compose.yml`,
    `docs/micro/20260916-docker-frontend-volume-mount/PLAN.md`.

- [~] **C13 — docs: architecture système et plan d'intégration Career Ops**
  - Ajout entier : `docs/CAREER_OPS_INTEGRATION_PLAN.md`,
    `docs/SYSTEM_ARCHITECTURE.md`,
    `docs/micro/20260915-integrate-global-ats/PLAN.md`,
    `docs/micro/DAILY_LOG-2026-09-15.md`, `docs/micro/DAILY_LOG-2026-09-16.md`.

- [ ] **C14 — chore: mise à jour uv.lock**
  - Ajout entier : `backend/uv.lock`.

- [ ] **Vérification finale** : `git status --porcelain=v1 -uall` vide,
  `cd backend && uv run pytest` vert, `git diff main..fix/profile-multi-sources --stat`
  comparé au diff initial (aucune perte).

- [ ] **Merge** : `git checkout main`, `git merge --no-ff fix/profile-multi-sources`.

- [ ] **Push** : `git push origin main` (demander confirmation avant, action à
  fort blast radius sur remote partagé).

- [ ] **Rebuild docker local** : reconstruire les images (`docker-compose.yml`
  modifié dans C12) et redémarrer les conteneurs.

## Code Review

- Dead code removed: n/a — opération de commit, aucun code modifié.
- Build status: à renseigner après C1..C14 (`uv run pytest`).
- Type errors: n/a côté backend Python ; `pnpm build` frontend si besoin de
  vérifier le TS après coup.
- Unintended side effects: vérifier que chaque `git apply --cached` partiel
  ne laisse pas de hunk orphelin (`git diff --cached` avant chaque commit).
- Security surface touched: oui (`auth`, `require_user_quota`, upload CV,
  validation d'URL) → lancer `mcp__plugin_semgrep_guardian__get_semgrep_sast_findings`
  et `get_semgrep_secrets_findings` une fois C1..C14 posés, avant le merge sur
  `main`.
- Verdict: à renseigner.

## Execution Log
- 2026-09-16 17:44 C1 committed (25304c6) — feat(usage-tracking): infrastructure API usage tracking et quotas
- 2026-09-16 17:48 C2 committed (65dd0a9) — feat(users): tier utilisateur et flag onboarding
- 2026-09-16 17:53 C3 committed (a54c349) — feat(cover-letter): prompts optimisés + tracking usage tokens
- 2026-09-16 17:57 C4 committed (66d4e64) — fix(llm): température des modèles de raisonnement
- 2026-09-16 18:01 C5 committed (4f90a35) — feat(pipeline): kanban, cadences de relance, résumé pipeline
- 2026-09-16 18:05 C6 committed (cce8863) — feat(evaluation): pipeline d'évaluation d'offre Two-Pass
- 2026-09-16 18:09 C7 committed (611a6bb) — feat(profile): sources multiples, préférences de ciblage, dédup projets
- 2026-09-16 18:12 C8 committed (ef5b286) — feat(cv-parser): extraction CV par VLM avec fallback texte
- 2026-09-16 18:16 C9 committed (7e5f462) — fix(crawler): robustesse extraction LLM en production
- 2026-09-16 18:20 C10 committed (d593e1b) — feat(ingestion): normalisation ville/entreprise/domaine
- 2026-09-16 18:23 C11 committed (96d2dfe) — feat(ui): sidebar, header, refonte landing RGPD
- 2026-09-16 18:26 C12 committed (5904992) — chore(docker): montage volume frontend en local

## Notes

- Fichiers vérifiés **mono-sujet** cette session (diff lu en entier, pas de
  split nécessaire) : `backend/app/routers/job_offers.py`,
  `backend/app/routers/users.py`, `backend/app/routers/__init__.py`,
  `backend/main.py`, `backend/app/services/cv_parser.py`,
  `backend/app/llm/utils.py`.
- Fichiers **scindés par hunk** : `backend/app/models.py` (C1/C2/C5/C6/C7),
  `backend/app/routers/cover_letters.py` (C3/C7).
- Fichier **bundlé par nécessité** (hunks à dépendance d'ordre d'exécution
  imbriquée, pas de split sûr) : `backend/app/routers/applications.py` → C5.
