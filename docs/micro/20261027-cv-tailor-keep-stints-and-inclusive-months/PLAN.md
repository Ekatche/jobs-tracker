---
task: CV adapté — un poste par entrée, intitulés et dates gardés par le profil, mois de fin inclus, accroche neutre sans permis
description: CV adapté (cv_tailor.py, cv_guards.py, cv_templates.py, tailor_prompt.md) — suppression de _merge_consecutive_stints et de la consigne de fusion des postes consécutifs chez le même employeur (progression interne perdue, intitulé récent collé sur la date de début la plus ancienne) ; verify_cv_honesty vérifie l'intitulé (role/title, _is_fuzzy_match) et les dates (_date_key/_end_key) de chaque expérience contre les postes du profil chez le même employeur ; _format_duration et _cumulative_career_years comptent le mois de fin (convention inclusive, 09/2017–08/2018 = 1 an, ancienneté 9 ans au lieu de 8), mois de fin inconnu = 1 ; accroche phrase 2 neutre (plus de « de la donnée … jusqu'à son usage final », plus de « principalement en ») et permis de conduire jamais dans l'accroche
status: blocked
created: 2026-10-27
---

# CV adapté : postes séparés, intitulés et dates vérifiés, mois inclusifs, accroche neutre

## Context
- Existing code checked:
  - `backend/app/services/cv_tailor.py:151-181` `_merge_consecutive_stints`, appelée par `enforce_page_budget` (ligne 201) ; docstring étape 1 « puis fusion des postes consécutifs ».
  - `backend/app/llm/prompts/cv/tailor_prompt.md` :
    - ligne 33, directive 2 (dates et entreprises, pas les intitulés) ;
    - ligne 40, phrase 2 de l'accroche « de la donnée ou de la matière de départ jusqu'à son usage final … principalement en … » ;
    - ligne 42, exemple data ;
    - ligne 60, « Fusionne les postes consécutifs chez le même employeur… » ;
    - ligne 86, directive 8 « cite-la dans l'accroche ».
  - `backend/app/services/cv_guards.py:130` `verify_cv_honesty` vérifie entreprises, compétences, formations et ancienneté. Il ne vérifie ni les intitulés ni les dates des postes.
  - `backend/app/services/cv_templates.py` :
    - `_format_duration` (103-141) : différence de mois exclusive ;
    - `_cumulative_career_years` (164-198) : mois de début inconnu = 1, mois de fin inconnu = 12, différence exclusive.
  - Retry de `generate_tailored_cv_content` (`cv_tailor.py:285-321`) : 2 tentatives, les violations sont renvoyées au LLM, puis `CVHonestyError`.
  - Preuve prod (lecture seule, CV `6ae0449281b393e4ffd03d40` du 27/10, offre Le Prado) :
    - les postes « Animatrice Permanente 3-11 ans » (2018-09 → 2022-08) et « Responsable Hub Leo 11-13 ans » (2022-09 → 2026-09) sont fusionnés en « Responsable Hub Leo 11-13 ans 2018-09 → 2026-09 » ;
    - l'accroche annonce « 8 ans » (cumul exclusif 107 mois ; inclusif 109 mois = 9 ans) ;
    - phrase 2 : « J'interviens de la mobilisation des jeunes jusqu'à la co-construction d'ateliers d'inclusion, titulaire du permis B, principalement avec les démarches partenariales et les outils numériques ».
- Fresh info looked up: n/a — logique métier et prompt, aucune bibliothèque.
- Git status checked:
  - renommages staged du balayage d'archive (3 plans CV du 26/10) et `docs/micro/INDEX.md` modifié par ce même balayage ;
  - non suivis hors périmètre, à ne jamais committer : `backend/.cache/`, `backend/scripts/transfer_user.py`, `backend/tests/test_transfer_user.py` ;
  - aucun fichier du périmètre modifié.

## Simpler Alternative Considered
- Restauration déterministe plutôt que garde : après le LLM, réécrire l'intitulé et les dates de chaque entrée depuis le poste du profil correspondant. Pas de retry, pas de coût LLM. Écartée : quand le LLM fusionne deux postes, rien ne dit lequel restaurer, et une garde explicite donne un message de correction au retry.
- Garder la fusion et seulement corriger les dates : la progression interne (animatrice puis responsable) reste invisible, or c'est l'argument principal du profil pour l'offre.

## Surgical Scope
- **Files touched**:
  - `backend/app/llm/prompts/cv/tailor_prompt.md`
  - `backend/app/services/cv_tailor.py`
  - `backend/app/services/cv_guards.py`
  - `backend/app/services/cv_templates.py`
  - `backend/tests/test_cv_tailor.py`
  - `backend/tests/test_cv_guards.py`
  - `backend/tests/test_cv_templates.py`
- **Files NOT touched**:
  - les gabarits HTML de CV (le regroupement visuel par employeur est un suivi possible, voir Notes) ;
  - `backend/app/routers/resumes.py` ;
  - le scoring des offres et le badge de pertinence ;
  - tout le reste.
- **Symbols replaced** (→ to delete before done):
  - `_merge_consecutive_stints` (`cv_tailor.py`) ;
  - `test_enforce_merges_consecutive_same_employer` et `test_enforce_keeps_non_consecutive_same_employer` (`test_cv_tailor.py`), remplacés par un test « postes consécutifs chez le même employeur gardés séparés ».
- **Symbols extended** (→ keep):
  - `enforce_page_budget` (retrait de l'appel et de la mention dans la docstring) ;
  - `verify_cv_honesty` (section 1 étendue aux intitulés et aux dates) ;
  - `_format_duration` et `_cumulative_career_years` (mois inclusifs) ;
  - `test_format_duration_unit`, `test_experience_duration_rendered_across_templates` et `test_cumulative_career_years_merges_overlaps_and_gaps` (valeurs attendues mises à jour) ;
  - `test_load_tailor_prompt_grounds_summary_in_profile_experiences` (`test_cv_tailor.py:297`) : l'assertion `prompt.count("principalement en") >= 2` épingle l'ancienne phrase 2. Elle devient `== 0`, et on ajoute une assertion sur la consigne du permis.

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.services.cv_tailor, app.services.cv_guards, app.services.cv_templates"` → exit 0
- [x] Tests pass (ciblés): `cd backend && uv run pytest tests/test_cv_tailor.py tests/test_cv_guards.py tests/test_cv_templates.py -v` → 0 failed
- [x] Tests pass (suite): `cd backend && uv run pytest tests` → 0 failed
- [x] Lint: `uvx flake8 backend/app/services/cv_tailor.py backend/app/services/cv_guards.py backend/app/services/cv_templates.py` (depuis la racine, config `.flake8`) → exit 0
- [x] Point 1, plus de fusion (code) : `grep -rn "_merge_consecutive_stints" backend/app backend/tests --include='*.py'` → aucune ligne
- [x] Point 1, plus de fusion (prompt) : `grep -c "Fusionne les postes" backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [x] Point 1, un poste par entrée demandé : `grep -c "une entrée par poste" backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 1
- [x] Point 2, garde (test) : `cd backend && uv run pytest tests/test_cv_guards.py -v -k "title or dates"` → au moins 3 tests sélectionnés et passés (intitulé inventé, dates d'un poste fusionné, intitulé reformulé ou dates illisibles acceptés)
- [x] Point 2, consigne prompt : `grep -c "intitulés de poste" backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 1
- [x] Point 3, durées inclusives : `cd backend && uv run python -c "from app.services.cv_templates import _format_duration as d; assert d('09/2017','08/2018')=='1 an'; assert d('09/2018','08/2022')=='4 ans'; assert d('09/2022','09/2026')=='4 ans 1 mois'; assert d('09/2018','09/2026')=='8 ans 1 mois'; assert d('03/2024','03/2024')=='1 mois'; assert d('2020','2022')=='2 ans'; assert d('2024','2021') is None; print('ok')"` → `ok`
- [x] Point 3, ancienneté du profil prod : `cd backend && uv run python -c "from app.services.cv_templates import _cumulative_career_years as c; p={'experiences':[{'start':'2017-09','end':'2018-08'},{'start':'2018-09','end':'2022-08'},{'start':'2022-09','end':'2026-09'}]}; assert int(c(p))==9; assert int(c({'experiences':[{'start':'2020','end':'2022'}]}))==2; print('ok')"` → `ok`
- [x] Point 4, phrase 2 neutre : `grep -c "de la donnée ou de la matière de départ" backend/app/llm/prompts/cv/tailor_prompt.md` → 0 et `grep -c "principalement en" backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [x] Point 4, permis hors accroche : `grep -c "cite-la dans l'accroche" backend/app/llm/prompts/cv/tailor_prompt.md` → 0 et `grep -c "Ne cite jamais le permis de conduire dans l'accroche" backend/app/llm/prompts/cv/tailor_prompt.md` → 1
- [x] Le prompt se formate toujours : `cd backend && uv run pytest tests/test_cv_tailor.py -v -k prompt` → 0 failed
- [x] No dead code: `_merge_consecutive_stints` et ses 2 tests absents (item point 1) ; pas d'import orphelin (flake8 F401)
- [x] Type check: n/a — pas de vérificateur de types dans le projet backend
- [ ] Manual check: déploiement sur accord de l'utilisateur (`docker compose -f docker-compose.prod.yml up -d --build backend`, `/docs` 200, mongodb résolu depuis le conteneur), puis l'utilisateur régénère le CV Le Prado (observateur : l'utilisateur). Il doit voir 3 entrées, dont 2 chez Léo Lagrange avec leurs intitulés et dates propres, les durées « 1 an », « 4 ans » et « 4 ans 1 mois », « 9 ans » dans l'accroche, et pas de permis dans l'accroche.

## Steps
- [x] Step 1 (point 3) : dans `cv_templates.py`, compter le mois de fin :
  - `_format_duration` au mois près : `total_months = diff + 1`, `None` si `diff < 0`. La branche « mois inconnu » (années entières) ne change pas.
  - `_cumulative_career_years` : somme des `end - start + 1` sur les intervalles fusionnés ; mois de fin inconnu = 1 au lieu de 12, pour qu'une paire « 2020 »–« 2022 » compte 2 ans comme `_format_duration`, et non 3.
  - Mettre à jour `test_format_duration_unit` (8 ans 1 mois, 1 an 1 mois, 7 mois, 4 mois, 1 an 7 mois, 2 ans 4 mois, et ajouter les cas du profil prod) et `test_experience_duration_rendered_across_templates` (« 8 ans 1 mois », « 6 mois »).
  - Mettre à jour `test_cumulative_career_years_merges_overlaps_and_gaps` (25/12, 50/12, 97/12) et y ajouter le profil prod (int 9) et la paire en années seules (int 2).
  - Les tests de garde d'ancienneté (`test_cv_guards.py`) doivent passer sans modification : 09/2018–07/2026 = 95 mois, soit 7 ans.
- [x] Step 2 (point 1) : supprimer `_merge_consecutive_stints` et son appel dans `enforce_page_budget`, et retirer « puis fusion des postes consécutifs » de la docstring. Remplacer les 2 tests de fusion par un test : 2 postes consécutifs chez le même employeur, avec des intitulés et des dates distincts, restent 2 entrées, dans l'ordre antichronologique, avec leurs intitulés et dates intacts.
- [x] Step 3 (point 2) : dans `verify_cv_honesty`, section 1, pour chaque expérience dont l'entreprise est reconnue :
  - postes du profil chez le même employeur = ceux dont `company`/`entreprise` passe `_is_fuzzy_match` ;
  - si au moins un a un `role`/`title`, l'intitulé adapté doit passer `_is_fuzzy_match` contre ces intitulés, sinon violation qui cite les intitulés connus ;
  - dates : au moins un poste candidat doit concorder. Début et fin sont lus avec `_date_key`/`_end_key` importés de `cv_templates`. Un côté illisible (année 0) concorde, une fin en cours d'un côté concorde. Sinon les années doivent être égales, et les mois aussi quand les deux sont connus.
  - Le message de violation liste les postes connus (« intitulé début → fin ») et dit : « reprends l'intitulé et les dates du profil, un poste par entrée, sans supprimer le poste ».
  - Une entreprise inventée garde sa seule violation actuelle (`continue`).
  - Tests ajoutés (noms contenant `title` ou `dates`) :
    - intitulé inventé : violation ;
    - entrée fusionnée « Responsable Hub » 2018-09 → 2026-09 contre les 2 postes du profil : violation de dates ;
    - intitulé raccourci (« Animatrice » pour « Animatrice Permanente 3-11 ans ») et profil sans dates : aucune violation.
  - Les 9 tests existants passent sans modification.
- [x] Step 4 (points 1, 2 et 4), prompt `tailor_prompt.md` :
  - directive 2 : ajouter les intitulés de poste aux éléments à ne jamais inventer ;
  - directive 4 : remplacer la consigne de fusion par « une entrée par poste du profil, même chez un employeur déjà cité, avec l'intitulé et les dates exacts du poste » ;
  - phrase 2 de l'accroche : « les publics, missions ou activités au cœur de son travail, tels que ses expériences les montrent ; ses outils ou méthodes principaux seulement s'ils servent l'offre ». Plus de « de … jusqu'à son usage final », plus de « principalement en ».
  - Réécrire la phrase 2 de l'exemple data pour qu'elle suive la nouvelle forme, sans « principalement en ».
  - directive 8 : garder l'habilitation exigée en tête de `certifications`. Elle peut figurer dans l'accroche, sauf le permis de conduire : « Ne cite jamais le permis de conduire dans l'accroche ».
  - Mettre à jour `test_load_tailor_prompt_grounds_summary_in_profile_experiences` : `"principalement en"` compte 0, et `"Ne cite jamais le permis de conduire dans l'accroche"` est présent. L'assertion `"CACES" in prompt` de `test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas` doit rester vraie : CACES reste cité en directive 8.
  - Lancer les tests de prompt.
- [x] Step 5 : lancer les 3 fichiers de tests ciblés, puis `cd backend && uv run pytest tests`. Si un test de génération de `test_cv_tailor.py` casse parce que la réponse LLM simulée contredit l'intitulé ou les dates de son profil, corriger la fixture, jamais la garde. Noter le cas dans Notes.
- [x] Step 6 (teardown) : scan d'orphelins borné à `_merge_consecutive_stints` (`grep -rn`, attendu 0), flake8 sur les 3 fichiers de service, puis remplir Code Review.
- [x] Step 7 (sur accord de l'utilisateur) : déployer le backend sur sentinel-vps avec `-f docker-compose.prod.yml`, vérifier `/docs` 200 et la résolution de mongodb, puis demander à l'utilisateur de régénérer le CV Le Prado.

## Code Review
- Dead code removed: yes — `_merge_consecutive_stints` et ses 2 tests supprimés ; `grep -rn _merge_consecutive_stints backend/app backend/tests` → 0 ligne ; flake8 (F401 compris) exit 0
- Build status: pass — import des 3 services exit 0 ; 3 fichiers ciblés 128 passed ; `uv run pytest tests` 1435 passed ; flake8 exit 0 ; les 7 grep du prompt conformes (0, 1, 1, 0, 0, 0, 1) ; vérifications point 3 → ok, ok
- Type errors: n/a — pas de vérificateur de types dans le backend
- Unintended side effects: frontière de `test_page_budget_by_career_years` décalée d'un mois ; une fin à l'année seule pèse 10 mois de moins dans le cumul ; un intitulé reformulé par le LLM déclenche le retry (un appel de plus). Voir Notes.
- Security surface touched: no
- Verdict: ⚠️ BLOCKED (en attente de l'utilisateur) — code et DoD automatiques verts ; l'étape 7 et le Manual check exigent un commit, un push et un déploiement décidés par l'utilisateur

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-27T07:31Z | claude-code | preflight | done | baseline logged in Notes
- 2026-10-27T07:31Z | claude-code | step 1 | started
- 2026-10-27T07:32Z | claude-code | step 1 | done | 3 fichiers ciblés 126 passed ; 2 vérifications point 3 (`uv run python -c`) → ok
- 2026-10-27T07:32Z | claude-code | step 2 | started
- 2026-10-27T07:33Z | claude-code | step 2 | done | `rtk grep -rn _merge_consecutive_stints backend/app backend/tests` exit 1 (0 référence) ; `test_cv_tailor.py` 28 passed, dont `test_enforce_keeps_consecutive_same_employer_stints_separate`
- 2026-10-27T07:33Z | claude-code | step 3 | started
- 2026-10-27T07:36Z | claude-code | step 3 | done | `uv run pytest tests/test_cv_guards.py -k "title or dates"` 3 passed ; fichier complet 14 passed (9 existants inchangés)
- 2026-10-27T07:36Z | claude-code | step 4 | started
- 2026-10-27T07:37Z | claude-code | step 4 | done | `uv run pytest tests/test_cv_tailor.py -k prompt` 8 passed ; prompt : 0 « principalement en », 1 « Ne cite jamais le permis de conduire dans l'accroche », CACES présent
- 2026-10-27T07:37Z | claude-code | step 5 | started
- 2026-10-27T07:40Z | claude-code | step 5 | done | 3 fichiers ciblés 128 passed ; `uv run pytest tests` 1435 passed (base 1433 + 3 gardes − 1 test de fusion fusionné) ; aucune fixture corrigée
- 2026-10-27T07:40Z | claude-code | step 6 | started
- 2026-10-27T07:45Z | claude-code | step 6 | done | grep `_merge_consecutive_stints` exit 1 (0 ligne) ; `uvx flake8` sur les 3 services exit 0 ; Code Review rempli
- 2026-10-27T07:45Z | claude-code | close | blocked | DoD automatiques verts (1435 passed, 128 ciblés, flake8 0, grep prompt conformes) ; étape 7 + Manual check en attente de commit/push/déploiement par l'utilisateur
- 2026-10-27T07:49Z | claude-code | step 7 | started | accord de l'utilisateur pour commit, push et déploiement
- 2026-10-27T07:51Z | claude-code | step 7 | done | commit 9638208 poussé ; VPS `git pull` + `docker compose -f docker-compose.prod.yml up -d --build backend` ; /docs 200, mongodb résolu (172.18.0.4), conteneur : `_merge_consecutive_stints` absent, `_dates_agree` présent, d('09/2017','08/2018') = « 1 an » ; régénération du CV Le Prado demandée à l'utilisateur

## Notes
- Fichiers de conventions lus : `CLAUDE.md` à la racine (`AGENTS.md` et `GEMINI.md` identiques, vérifié avec `cmp`). Pas de fichier de conventions sous `backend/`.
- Point de départ (27/10, 07:31 UTC, avant toute modification) :
  - build : exit 0 ;
  - flake8 : exit 0 ;
  - 3 fichiers ciblés : 126 passed ;
  - `uv run pytest tests` : 1433 passed ;
  - `_merge_consecutive_stints` présent (`cv_tailor.py:151` et `:201`) ;
  - grep sur le prompt, dans l'ordre des items DoD : 1, 0, 0, 1, 2, 1, 0 ;
  - point 3 en échec attendu : `d('09/2017','08/2018')` vaut « 11 mois », et le cumul du profil prod 8,83.
- Étape 1, écart : `test_page_budget_by_career_years` (`test_cv_tailor.py`), pas prévu dans Symbols extended, a cassé. Son cas « juste sous 5 ans », 2017-02 → 2022-01, fait 60 mois en convention inclusive, donc 2 pages.
  - Correction : le cas « sous 5 ans » passe à 2017-03 → 2022-01 (59 mois, 1 page), et 2017-02 → 2022-01 devient le cas « 5 ans pile » (2 pages). La frontière reste testée des deux côtés.
- Étape 7 (déploiement) : le VPS déploie le code poussé. Il faut donc un commit et un push, que seul l'utilisateur décide. L'exécution s'arrête avant l'étape 7 et la demande.
- Coût : une violation d'intitulé ou de dates déclenche le retry existant, soit un appel LLM de plus. Les seuils tolérants de l'étape 3 (sous-chaîne et ratio 0,85 sur l'intitulé, dates illisibles ou en cours acceptées) limitent les faux positifs. Le prompt demande désormais explicitement intitulés et dates exacts, ce qui devrait garder le taux de retry bas. À surveiller dans les logs : « CV honesty verification failed ».
- La convention inclusive (09/2017–08/2018 = 12 mois) est celle de LinkedIn et des CV. La convention exclusive, gardée par erreur à la revue du 26/10, sous-comptait d'un mois chaque poste.
- Suivi possible, hors périmètre : regrouper visuellement dans les gabarits les postes consécutifs d'un même employeur (un en-tête employeur, deux intitulés datés).
- Statut `blocked` le 27/10 : rien n'échoue. Étape 7 faite (commit 9638208 déployé en prod). Seul le Manual check reste : l'utilisateur régénère le CV Le Prado et confirme 3 entrées, dont 2 chez Léo Lagrange, « 1 an » / « 4 ans » / « 4 ans 1 mois », « 9 ans » dans l'accroche, pas de permis dans l'accroche. Prochaine action : sur sa confirmation, cocher le Manual check et passer `status: done`.
- Point 5 (diplôme obligatoire absent : DEES pour Le Prado) différé par l'utilisateur.
- Étape 3 : un poste du profil sans intitulé reste candidat (intitulé non vérifié, dates vérifiées) ; un poste sans entreprise n'est jamais rattaché (`_is_fuzzy_match` ignore les valeurs vides du profil).
- Étape 4, écart rattrapé en phase 7 : la consigne commençait par « Une entrée par poste », et l'item DoD `grep -c "une entrée par poste"` (sensible à la casse) renvoyait 0. Reformulée en « Garde une entrée par poste… », sans changer le sens.
- Étape 6 : un premier flake8 a été lancé avec `--max-line-length=130`, ce qui n'est pas la commande du DoD. Il a été relancé tel que le DoD l'écrit, depuis la racine avec la config `.flake8` : exit 0.
- Effet de bord assumé (étape 1) : avec la convention inclusive, une fin à l'année seule compte maintenant le mois 1 de cette année, et non plus le mois 12.
  - Exemple : « 2020 » – « 2022 » passe de 35 à 25 mois. Le nombre d'années entières reste 2, et cela concorde avec `_format_duration`.
  - Un profil daté à l'année seule perd jusqu'à 10 mois de cumul, ce qui touche le budget de pages et le plafond d'ancienneté de l'accroche.
- Risque à surveiller : les consignes « réaligne le vocabulaire métier sur l'offre » (directive 4) peuvent pousser le LLM à renommer un intitulé. La garde le rejette alors et déclenche le retry. Le message de violation dit « sans supprimer le poste », pour contrer le « Retire ces éléments » du texte de retry générique.
