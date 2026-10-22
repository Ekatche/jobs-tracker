---
task: CV adapté — budget de pages selon l'expérience et puces réparties par pertinence pour l'offre
description: tailored CV page budget by career length and offer seniority instead of strict one page — cv_tailor.py compute_page_budget (career span from profile experiences start/end with cv_templates._date_key/_end_key, 2 pages from 5 years of career (TWO_PAGES_FROM_YEARS, offer seniority ignored — user decision at step 6), else 1 page; bullets 10/22, projects 2/3), enforce_page_budget replaces enforce_one_page_limits (no rank caps, no MAX_EXPERIENCES drop, relevance principale/secondaire, trim oldest secondary first, principal floor 2 bullets, protect bullets citing critical/high Bloc B matched_requirements, log each cut), TailoredExperienceItem.relevance in models.py, tailor_prompt.md placeholders {page_limit} {bullet_budget} {max_projects} and relevance in JSON schema; pytest test_cv_tailor
status: done
created: 2026-10-22
---

# CV adapté — budget de pages selon l'expérience et puces réparties par pertinence

## Context
- Existing code checked:
  - `backend/app/services/cv_tailor.py` (non commité, produit par le plan `archive/2026-10/20261022-tailored-cv-one-page-limits`) : constantes L97-102 (`MAX_EXPERIENCES = 6`, `BULLETS_BY_RANK = [4, 3, 2]`, `MAX_TECHNOLOGIES`, `MAX_PROJECTS`, `MAX_SKILL_GROUPS`, `MAX_SKILLS_PER_GROUP`), `_merge_consecutive_stints` L105, `enforce_one_page_limits` L137, appel L238 après `verify_cv_honesty`. `load_tailor_prompt(profile, offer, evaluation)` L41-94 fait `template.format(...)` avec 6 clés.
  - Ce code répartit les puces par **rang chronologique** (4/3/2 puis rien) et **supprime** au-delà de 6 expériences : une expérience ancienne mais centrale pour l'offre perd ses preuves, et un trou apparaît dans le parcours. C'est ce que ce plan corrige.
  - `backend/app/services/cv_templates.py` : `_date_key` L74 (année, mois) d'une date libre, `_end_key` L87 (« Présent », vide → (9999, 12)), `_most_recent_first` L106 (ordre du rendu PDF).
  - `backend/app/models.py` : `CandidateExperience` L499 (dates du profil en `start` / `end`), `TailoredExperienceItem` L702 (pas de champ de pertinence). Le profil de test `SAMPLE_PROFILE` (test_cv_tailor.py L33) utilise `start_date` / `end_date` : lire les deux formes.
  - Offre : `seniority_level` (junior, mid, senior, lead, director, intern) posé par `extract_seniority` à la collecte ; `routers/resumes.py` L140 passe le document Mongo `offer_doc` brut, donc `offer.get("seniority_level")` est disponible (peut être absent).
  - Bloc B : `evaluation["bloc_b"]["matched_requirements"]` porte `requirement` et `weight` (critical, high, meaningful) ; `candidate_evidence` est du texte libre, sans lien structuré vers une expérience.
  - Usages de `enforce_one_page_limits`, `BULLETS_BY_RANK`, `MAX_EXPERIENCES` : uniquement `cv_tailor.py` et `tests/test_cv_tailor.py` (L15-17, tests L328-543).
- Fresh info looked up: n/a — logique métier, aucune API externe. Repère recrutement retenu avec l'utilisateur : une page tant que le parcours fait moins de 10 ans, deux pages au-delà (ou dès 5 ans pour un poste senior, lead ou director).
- Git status checked: `cv_tailor.py`, `tailor_prompt.md`, `test_cv_tailor.py` portent les changements non commités du plan `20261022-tailored-cv-one-page-limits` ; `models.py` porte aussi `ApiUsageAction.LETTER_REWRITE` du plan `20261022-letter-partial-rewrite`. Commiter ces plans **avant** d'exécuter celui-ci, pour que son diff reste lisible.

## Simpler Alternative Considered
Garder `enforce_one_page_limits` et relever seulement les plafonds (5/4/3, 8 expériences). Rejeté : la répartition resterait chronologique, donc une mission ancienne qui prouve une exigence critique de l'offre resterait sacrifiée, et la suppression d'expériences laisserait des trous. Le LLM juge déjà la pertinence avec Bloc B ; le code ne fait que tenir le budget sans contredire ce jugement.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py` (champ `relevance` dans `TailoredExperienceItem`)
  - `backend/app/services/cv_tailor.py`
  - `backend/app/llm/prompts/cv/tailor_prompt.md`
  - `backend/tests/test_cv_tailor.py`
- **Files NOT touched**: tous les autres — en particulier `cv_templates.py` et `templates/cv/*.html` (l'ordre des sections fera l'objet d'un plan séparé), `cv_guards.py`, `routers/resumes.py`, le frontend.
- **Symbols replaced** (→ to delete before done): `enforce_one_page_limits`, `BULLETS_BY_RANK`, `MAX_EXPERIENCES`, `MAX_PROJECTS` ; tests `test_enforce_caps_bullets_by_rank`, `test_enforce_drops_oldest_beyond_max`.
- **Symbols extended** (→ keep): `_merge_consecutive_stints` (pertinence fusionnée), `load_tailor_prompt` (paramètre `budget`), `generate_tailored_cv_content`, `MAX_TECHNOLOGIES`, `MAX_SKILL_GROUPS`, `MAX_SKILLS_PER_GROUP`, `TailoredExperienceItem` ; tests `test_enforce_sorts_like_renderer`, `test_enforce_merges_consecutive_same_employer`, `test_enforce_keeps_non_consecutive_same_employer`, `test_enforce_caps_projects_skills_technologies`, `test_enforce_leaves_short_cv_unchanged`, `test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas`.
- **Symbols created**: `PageBudget`, `compute_page_budget`, `_career_years`, `enforce_page_budget`, `_is_protected`, constantes `PAGE_BUDGETS`, `SENIOR_LEVELS`, `MAX_PRINCIPAL_BULLETS`, `MAX_SECONDARY_BULLETS`, `MIN_PRINCIPAL_BULLETS`.

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.services.cv_tailor, app.routers.resumes"`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cv_tailor.py tests/test_resumes_api.py tests/test_cv_guards.py -q`
- [x] No dead code: `grep -rlE --include='*.py' 'enforce_one_page_limits|BULLETS_BY_RANK|MAX_EXPERIENCES|MAX_PROJECTS\b' backend/app backend/tests | wc -l` → 0
- [x] Type check: n/a — aucun type checker configuré côté backend
- [x] Budget selon l'ancienneté (1 page < 5 ans ; 2 pages ≥ 5 ans, quel que soit le niveau de l'offre — règle modifiée au Step 6 sur décision de l'utilisateur, à l'origine 10 ans ou 5 ans avec offre senior/lead/director) : `cd backend && uv run pytest tests/test_cv_tailor.py -k page_budget -q` → au moins 4 passed
- [x] Aucune expérience supprimée, quel que soit leur nombre : `cd backend && uv run pytest tests/test_cv_tailor.py -k never_drops -q` → 1 passed
- [x] Puces coupées d'abord sur les expériences secondaires les plus anciennes, principales jamais sous 2 puces : `cd backend && uv run pytest tests/test_cv_tailor.py -k trims_secondary_before_principal -q` → 1 passed
- [x] Une puce qui cite une exigence critical ou high n'est jamais coupée : `cd backend && uv run pytest tests/test_cv_tailor.py -k keeps_bullets_citing -q` → 1 passed
- [x] Sans pertinence fournie par le LLM, l'expérience la plus récente est traitée comme principale : `cd backend && uv run pytest tests/test_cv_tailor.py -k defaults_most_recent -q` → 1 passed
- [x] Chaque coupe est journalisée : `cd backend && uv run pytest tests/test_cv_tailor.py -k logs_each_cut -q` → 1 passed
- [x] Prompt sans plafonds par rang ni suppression d'expériences ni « une page pour tous » : `grep -cE 'omets les plus anciennes|pour tous les profils|rang 1|quatrième expérience' backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [x] Prompt piloté par le budget calculé : `grep -cE '\{page_limit\}|\{bullet_budget\}|\{max_projects\}' backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 3
- [x] Pertinence demandée au LLM dans le schéma JSON : `grep -c '"relevance"' backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 1
- [x] Manual check: voir Step 6 (observateur nommé : l'utilisateur)

## Steps
- [x] Step 1: `models.py` — ajouter à `TailoredExperienceItem` : `relevance: Optional[str] = Field(default=None, description="« principale » si l'expérience prouve des exigences de l'offre, sinon « secondaire »")`. Type `str` et non `Literal` : une valeur inattendue du LLM (« Principale », « primary ») ne doit pas faire échouer la validation et renvoyer un 422 ; le code compare en casefold.
- [x] Step 2: `cv_tailor.py` — budget :
  - importer `_date_key`, `_end_key` depuis `app.services.cv_templates` (à côté de `_most_recent_first`) et `NamedTuple` / `date` ;
  - `class PageBudget(NamedTuple): pages: int; bullets: int; projects: int` ;
  - `PAGE_BUDGETS = {1: PageBudget(1, 10, 2), 2: PageBudget(2, 22, 3)}`, `SENIOR_LEVELS = {"senior", "lead", "director"}` ;
  - `_career_years(profile) -> float` : pour chaque expérience du profil, début = `_date_key(exp.get("start") or exp.get("start_date"))` (ignorer `(0, 0)`), fin = `_end_key(exp.get("end") or exp.get("end_date"))` avec `(9999, 12)` remplacé par l'année et le mois du jour ; mois 0 → 1 pour un début, 12 pour une fin ; retourne (fin la plus tardive − début le plus ancien) en mois / 12, 0 si aucun début daté ;
  - `compute_page_budget(profile, offer) -> PageBudget` : 2 pages si `years >= 10`, ou si `years >= 5` et `(offer.get("seniority_level") or "").casefold() in SENIOR_LEVELS` ; sinon 1 page ;
  - tests `test_page_budget_*` avec des dates de fin explicites (jamais « Présent », pour que le résultat ne dépende pas de la date du jour) : 2018–2022 sans niveau → 1 ; 2010–2021 → 2 ; 2015–2021 + `senior` → 2 ; 2015–2021 + `junior` → 1 ; profil sans date → 1.
- [x] Step 3: `cv_tailor.py` — remplacer `enforce_one_page_limits` par `enforce_page_budget(cv, budget, evaluation=None)`, et supprimer dans la même étape `enforce_one_page_limits`, `BULLETS_BY_RANK`, `MAX_EXPERIENCES`, `MAX_PROJECTS` (remplacé par `budget.projects`) :
  1. tri `_most_recent_first` puis `_merge_consecutive_stints` (étendu : `relevance` = « principale » si l'un des deux postes fusionnés l'est) ;
  2. principale = `(exp.relevance or "").strip().casefold() == "principale"` ; si aucune ne l'est, la plus récente devient principale ;
  3. plafonds : principale `MAX_PRINCIPAL_BULLETS = 5`, secondaire `MAX_SECONDARY_BULLETS = 2`, technologies `MAX_TECHNOLOGIES` ; une entrée sans puce perd aussi ses technologies (entrée compacte) ;
  4. si le total de puces dépasse `budget.bullets` : retirer la dernière puce **non protégée** des secondaires, de la plus ancienne à la plus récente, puis des principales de la plus ancienne à la plus récente sans descendre sous `MIN_PRINCIPAL_BULLETS = 2` ; s'arrêter dès que le budget est tenu ; si seules des puces protégées restent, garder le dépassement et le journaliser en warning ;
  5. `_is_protected(bullet, terms)` : `terms` = `requirement` casefold des `matched_requirements` de poids `critical` ou `high` ; vrai si `re.search(rf"(?<!\w){re.escape(term)}(?!\w)", bullet.casefold())` pour un terme ;
  6. projets `[: budget.projects]`, compétences `MAX_SKILL_GROUPS` × `MAX_SKILLS_PER_GROUP` (inchangé) ;
  7. aucune expérience retirée ; chaque puce coupée journalisée en `logger.info` avec l'entreprise.
  Dans `generate_tailored_cv_content` : `budget = compute_page_budget(profile, offer)` avant la boucle, passé à `load_tailor_prompt` et à `return enforce_page_budget(tailored_cv, budget, evaluation)`.
- [x] Step 4: `tailor_prompt.md` et `load_tailor_prompt` :
  - `load_tailor_prompt(profile, offer, evaluation=None, budget=None)` ; `budget = budget or compute_page_budget(profile, offer)` ; ajouter à `template.format` : `page_limit` (« Une page A4 » ou « Deux pages A4 »), `bullet_budget`, `max_projects` ;
  - directive 4 : garder l'ordre antichronologique, la fusion des postes consécutifs, « une puce = une ligne, environ 20 mots », 6 outils ; remplacer les plafonds par rang et la ligne « 6 expériences au maximum… » par :
    - « Budget total : {bullet_budget} puces pour l'ensemble des expériences, réparties selon la pertinence pour l'offre et l'analyse Bloc B, pas selon l'ancienneté. » ;
    - « Indique pour chaque expérience `relevance` : « principale » si elle prouve des exigences de l'offre (en priorité de poids critical ou high), sinon « secondaire ». » ;
    - « Expérience principale : 5 puces au maximum, en commençant par celles qui prouvent les exigences de l'offre. Une expérience ancienne mais centrale pour l'offre peut recevoir plus de puces qu'une expérience récente. » ;
    - « Expérience secondaire : 0 à 2 puces ; sans lien avec l'offre, garde-la en entrée compacte (bullet_points: [] et relevant_technologies: []) avec titre, entreprise, lieu et dates. » ;
    - « Ne supprime aucune expérience : un trou dans le parcours pèse plus qu'une ligne de plus. » ;
  - directive 6 : « Sélectionne 0 à {max_projects} projets… » ;
  - directive 9 : « {page_limit} au maximum. Pour tenir ce budget, raccourcis d'abord les expériences secondaires les plus anciennes, puis les projets ; garde les puces qui prouvent les exigences de poids critical ou high. » ;
  - schéma JSON, objet expérience : ajouter `"relevance": "principale ou secondaire",` (accolades du schéma restent doublées).
- [x] Step 5: `test_cv_tailor.py` :
  - supprimer `test_enforce_caps_bullets_by_rank`, `test_enforce_drops_oldest_beyond_max` et les imports `enforce_one_page_limits`, `MAX_EXPERIENCES`, `BULLETS_BY_RANK` ;
  - porter les 5 tests `test_enforce_*` conservés sur `enforce_page_budget(cv, PAGE_BUDGETS[1])` ; dans le test de fusion, vérifier que la pertinence fusionnée vaut « principale » si l'un des postes l'est ;
  - ajouter `test_enforce_never_drops_experiences` (8 expériences → 8), `test_enforce_trims_secondary_before_principal`, `test_enforce_keeps_bullets_citing_critical_requirements` (avec `SAMPLE_EVALUATION`), `test_enforce_defaults_most_recent_to_principal`, `test_enforce_logs_each_cut` (`caplog`) ;
  - `test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas` : remplacer l'assertion « Une page A4 » par le budget rendu pour `SAMPLE_PROFILE` / `SAMPLE_OFFER`, vérifier l'absence de `{page_limit}` non rendu ; ajouter un cas offre `senior` + profil 2010–2021 → « Deux pages A4 » et « 0 à 3 projets ».
  - lancer la commande « Tests pass » du Definition of Done.
- [x] Step 6 (vérification manuelle, observateur : l'utilisateur) : générer un CV pour une offre réelle avec son profil, ouvrir le PDF. Vérifier : nombre de pages conforme au budget annoncé ; les expériences qui prouvent les exigences de l'offre sont les plus détaillées ; aucune expérience du profil ne manque ; aucune page à moitié vide. Si le PDF déborde, réduire `PAGE_BUDGETS` (10 → 9 puces) et noter la valeur retenue dans `## Notes`.
- [x] Step 7 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the replaced symbols (commande « No dead code » du Definition of Done). Confirm 0 orphans.

## Code Review
- Dead code removed: yes — `enforce_one_page_limits`, `BULLETS_BY_RANK`, `MAX_EXPERIENCES`, `MAX_PROJECTS`, `SENIOR_LEVELS` (créé puis retiré au Step 6), `test_enforce_caps_bullets_by_rank`, `test_enforce_drops_oldest_beyond_max` ; scan borné → 0
- Build status: pass — import exit 0 ; `pytest test_cv_tailor test_resumes_api test_cv_guards -q` 55 passed (46 au départ) ; les 6 `-k` ciblés passent ; 3 grep du prompt conformes (0 / 3 / 1)
- Type errors: none — pas de type checker ; `ruff --select F401,F841` propre sur les deux fichiers Python (l'import inutilisé `BULLETS_BY_RANK` de la base a disparu). Le seul signalement, E303 à `cv_tailor.py:30`, existait déjà dans la copie de base : laissé en place, hors périmètre
- Unintended side effects: none — diff lu ligne à ligne contre `scratchpad/baseline/` : chaque ligne relève d'un step. `compute_page_budget` n'a qu'un argument depuis le Step 6, et aucun appel à 2 arguments ne subsiste. Les CV déjà stockés (sans `relevance`) restent inchangés, car le post-traitement ne tourne qu'à la génération. Les tests ajoutés sont des fonctions pures, sans base ni réseau
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-22T18:50Z | claude-code | preflight | done | baseline recorded in Notes
- 2026-10-22T18:50Z | claude-code | step 1 | started
- 2026-10-22T18:52Z | claude-code | step 1 | done | TailoredExperienceItem().relevance → None, relevance='Principale' accepté, exit 0
- 2026-10-22T18:52Z | claude-code | step 2 | started
- 2026-10-22T18:53Z | claude-code | step 2 | done | `pytest tests/test_cv_tailor.py -k page_budget -q` 5 passed
- 2026-10-22T18:53Z | claude-code | step 3 | started
- 2026-10-22T18:56Z | claude-code | step 3 | done | build exit 0 ; `pytest tests/test_cv_tailor.py -q` 19 passed ; No dead code → 0
- 2026-10-22T18:56Z | claude-code | step 4 | started
- 2026-10-22T18:57Z | claude-code | step 4 | done | build exit 0 ; 19 passed ; anciennes règles 0 ; placeholders 3 ; `"relevance"` 1 ; prompt rendu sans placeholder résiduel
- 2026-10-22T18:57Z | claude-code | step 5 | started
- 2026-10-22T18:59Z | claude-code | step 5 | done | `pytest test_cv_tailor test_resumes_api test_cv_guards -q` 55 passed ; -k page_budget 6, never_drops 1, trims_secondary_before_principal 1, keeps_bullets_citing 1, defaults_most_recent 1, logs_each_cut 1
- 2026-10-22T18:59Z | claude-code | step 6 | waiting | vérification manuelle demandée à l'utilisateur
- 2026-10-22T19:17Z | claude-code | step 6 | adjusted | décision utilisateur « 2 pages dès 5 ans » appliquée ; build exit 0 ; DoD tests 55 passed ; -k page_budget 6 passed ; profil réel 8,8 ans → PageBudget(2, 22, 3)
- 2026-10-22T19:22Z | claude-code | step 6 | done | CV régénéré par l'utilisateur (19:19Z, Solvay « Data Science », `creatif`) rendu dans le conteneur : 2 pages (page 1 93 %, page 2 84 %), 7/7 expériences, 16 puces / 22, 2 projets ; « ok parfait » de l'utilisateur sur la règle
- 2026-10-22T19:22Z | claude-code | step 7 | started
- 2026-10-22T19:23Z | claude-code | step 7 | done | `find_symbol(enforce_one_page_limits)` not found ; No dead code → 0 ; `SENIOR_LEVELS` → 0 ; anciens tests → 0 ; appels `compute_page_budget` à 2 arguments → 0
- 2026-10-22T19:25Z | claude-code | close-out | done | DoD complet relancé : build exit 0 ; 55 passed ; -k page_budget 6, never_drops 1, trims_secondary_before_principal 1, keeps_bullets_citing 1, defaults_most_recent 1, logs_each_cut 1 ; No dead code 0 ; prompt 0 / 3 / 1 ; diff lu contre la base

## Notes
- Valeurs de budget (10 puces / 1 page, 22 / 2 pages) à calibrer au Step 6 : elles dépendent de la longueur réelle des puces et du modèle de CV choisi.
- La protection des puces repose sur une correspondance littérale du libellé de l'exigence : une exigence longue (« 3 ans d'expérience en Python ») ne protège rien. Le prompt reste la première ligne de défense ; le code est un filet.
- Les CV déjà stockés n'ont pas de `relevance` (None) : sans effet, le post-traitement ne tourne qu'à la génération.
- Hors périmètre, plan séparé à proposer : remonter les compétences juste après l'accroche dans `classique`, `creatif` et `executive_minimalist`, pour qu'elles restent en page 1 sur un CV de deux pages.
- Conventions lues (Phase 3) : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`) — tests pertinents, procédure `tests_for` avant suppression de tests ; `.cursorrules` — graphe code-review-graph d'abord. `tests_for(enforce_one_page_limits)` : 7 tests `test_enforce_*` (test_cv_tailor.py L328-545) + 4 tests indirects de `test_cv_guards.py`.
- Base (2026-10-22T18:50Z, avant toute modification) : build exit 0 ; `pytest test_cv_tailor test_resumes_api test_cv_guards` 46 passed ; les 6 `pytest -k` ciblés ne trouvent aucun test ; No dead code 5 fichiers (dont 3 `.pyc` de `__pycache__`) ; anciennes règles du prompt 4 ; placeholders 0 ; `"relevance"` 0.
- Correction de la commande « No dead code » : ajout de `--include='*.py'`, sinon les `.pyc` périmés de `__pycache__` font échouer le critère. Le critère lui-même est inchangé.
- Les fichiers du périmètre portaient déjà les changements non commités des plans `20261022-tailored-cv-one-page-limits` et `20261022-letter-partial-rewrite` au démarrage ; copie de base dans le scratchpad de session (`scratchpad/baseline/`) pour isoler le diff de ce plan.
- Step 3 : la migration des tests existants (imports, suppression de `test_enforce_caps_bullets_by_rank` et `test_enforce_drops_oldest_beyond_max`, 5 tests portés sur `enforce_page_budget(cv, PAGE_BUDGETS[1])`) a été avancée du Step 5 au Step 3, sinon le Dead Code Gate de ce step ne pouvait pas passer. Le Step 5 garde l'ajout des nouveaux tests et l'assertion de pertinence fusionnée.
- Step 3 : helper `_is_principal(exp)` ajouté (non listé dans « Symbols created ») pour éviter de répéter la comparaison casefold dans `_merge_consecutive_stints` et `enforce_page_budget`. La protection des puces s'applique aussi aux plafonds 5/2, pas seulement au budget total, pour tenir le critère « une puce qui cite une exigence critical ou high n'est jamais coupée ».
- Step 4 : `budget` annoté `Optional["PageBudget"]` (référence avant définition) : `PageBudget` est déclaré après `load_tailor_prompt` dans le module.
- Step 5 : `test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas` vérifiait « 0 à 2 projets » et l'absence de « deux pages » en dur ; remplacé par le budget calculé pour `SAMPLE_PROFILE` (fin « Présent », donc dépendant de la date du jour), pour que le test ne casse pas quand le profil de test franchira 10 ans.
- Step 6, observation 1 (CV généré à 2026-10-22T19:06Z, nouveau code) : offre Consort Group « Data Analyst » (Microsoft BI : SQL, SSIS/SSAS/SSRS, Power BI, qualité de données), pas d'évaluation Bloc B, modèle `sidebar_elegance`. Parcours 2018-2026 → budget 1 page / 10 puces / 2 projets. Les 7 expériences sont gardées, 10 puces (3/2/2/1/2/0/0), choix des puces cohérent avec l'offre (BI, ETL, KPI ; RAG laissé de côté à juste titre). **Le PDF déborde** : page 1 pleine à 89 %, page 2 = projets seuls (21 %). Cause : dans ce modèle une puce d'environ 20 mots tient sur 2 lignes, donc 10 puces ≈ 20 lignes, et chaque expérience ajoute en-tête et ligne d'outils. L'utilisateur demande que ses expériences soient bien racontées dans les puces : réduire à 9 puces (consigne du Step 6) ne suffit pas et appauvrirait encore les expériences. Décision de politique de pages demandée à l'utilisateur.
- Step 6, décision de l'utilisateur (2026-10-22T19:15Z) : « 2 pages dès 5 ans ». `compute_page_budget(profile)` ne prend plus l'offre ; `SENIOR_LEVELS` supprimé, remplacé par `TWO_PAGES_FROM_YEARS = 5`. Tests du budget réécrits (4 ans → 1, 4 ans 11 mois → 1, 5 ans → 2, 11 ans → 2, sans date → 1) ; test du prompt renommé `test_load_tailor_prompt_renders_one_and_two_page_budgets` (cas 1 page et cas 2 pages).
- Prochaine action : l'utilisateur régénère son CV pour une offre ; mesurer le PDF (pages, remplissage de la dernière page) ; puis Step 7 et Phase 7.
- Step 6, observation 2 (CV généré à 2026-10-22T19:19Z, règle « 2 pages dès 5 ans ») : offre Solvay « Data Science », modèle `creatif`, budget 2 pages / 22 puces / 3 projets. PDF : 2 pages, page 1 remplie à 93 %, page 2 à 84 %, pas de page à moitié vide. Puces : principales Nile 4, CLB 4, Bimedoc 3, Nodya 2 ; secondaires bioMérieux 2, Sanofi 1, Framatome 0 (entrée compacte). 16 puces sur 22 : sous le budget total (les coupes éventuelles des plafonds 5/2 ne sont pas visibles, logs en WARNING). 2 projets, 7/7 expériences. `PAGE_BUDGETS` conservé tel quel (10 / 22), pas de recalibrage.
- Close-out : le code de ce plan est **déjà commité**, pendant l'exécution et pas par cette session. Les deux commits datent de 2026-10-22T19:18Z, juste après l'ajustement du Step 6, et ne sont pas poussés (main est à ahead 3).
  - `a0d1a54` « feat(cv): enforce strict one page limits » contient `cv_tailor.py`, `tailor_prompt.md` et `test_cv_tailor.py` avec `enforce_page_budget` et `TWO_PAGES_FROM_YEARS`.
  - `cc18bbe` « feat(letters)… » contient le champ `relevance` de `models.py`.
  - Les messages de ces commits ne décrivent pas ce plan. Seul le dossier du plan reste non suivi.
