---
task: Calibrer la génération de CV pour 1 page stricte et regrouper les expériences
description: tailored CV strict one page for every profile — cv_tailor.py enforce_one_page_limits post-processor after verify_cv_honesty, experiences sorted with cv_templates._most_recent_first (same order as PDF render), consecutive same-employer stints merged (casefold company, oldest start_date, newest end_date), bullet caps by rank 4/3/2 then compact entries (no bullets, no technologies), max 6 experiences, max 6 relevant_technologies, max 2 featured_projects, max 4 skill groups × 8 skills; tailor_prompt.md directives 4 5 6 9 rewritten (antichronologique, remove "ne la supprime jamais" and "deux pages"); pytest test_cv_tailor
status: done
created: 2026-10-22
---

# Calibrer la génération de CV pour 1 page stricte et regrouper les expériences

## Context
- Existing code checked:
  - `backend/app/llm/prompts/cv/tailor_prompt.md`, rendu par `load_tailor_prompt` via `template.format` (accolades littérales doublées, ex. schéma JSON en `{{ }}`). Directive 4 : 4 à 5 puces par expérience pertinente, 1 à 2 pour une annexe, « ne la supprime jamais » (L55). Directive 5 : 2 à 4 catégories. Directive 6 : 0 à 3 projets (L72). Directive 9 : « Une page A4 [...] ; deux pages maximum sinon » (L84). Aucun ordre imposé aux expériences.
  - `backend/app/services/cv_tailor.py::generate_tailored_cv_content` : 2 tentatives ; `verify_cv_honesty` (L144) puis `return tailored_cv` (L146). Seul appelant : `routers/resumes.py:140` (`CVHonestyError` → 422).
  - `backend/app/services/cv_guards.py:142` : toute entreprise absente du profil est une violation. Une « ligne de synthèse » générée par le LLM (ex. « Expériences antérieures — Divers ») échouerait donc au contrôle d'honnêteté. D'où les entrées compactes, qui gardent titre, entreprise et dates réels.
  - `backend/app/services/cv_templates.py::_most_recent_first` (L106) : `render_cv_html` (L136) **retrie déjà** les expériences par date au rendu. Les plafonds par rang doivent suivre cet ordre, sinon « rang 0 » dans le JSON ne serait pas le premier poste affiché. On réutilise ce tri, sans nouvelle analyse de date.
  - `backend/app/models.py:702` : `TailoredExperienceItem` (`title`, `company`, `start_date` requis ; `location`, `end_date`, `bullet_points`, `relevant_technologies` optionnels ou en listes). Pydantic 2.11 (`model_dump`, `model_copy`).
  - `backend/app/templates/cv/{classique,creatif,executive_minimalist,sidebar_elegance}.html` : `{% if exp.bullet_points %}` et ligne d'outils seulement si `relevant_technologies` est renseigné. Une entrée compacte s'affiche donc en en-tête seul.
  - `backend/tests/test_cv_tailor.py:229-233` vérifie « 4 à 5 bullet points », « 1 à 2 bullet points », « 0 à 3 projets », « Une page A4 ». La fixture `VALID_LLM_OUTPUT` (2 expériences, 2 puces et 1 puce) reste sous les plafonds.
- Fresh info looked up: n/a (logique métier, prompt et post-traitement Pydantic).
- Git status checked: `tailor_prompt.md`, `cv_tailor.py` et `test_cv_tailor.py` sont propres. Le travail PDF de la lettre, non commité, ne touche aucun de ces fichiers.

## Simpler Alternative Considered
- Prompt seul : rejeté. Les LLM ignorent par intermittence les contraintes de longueur et produisent encore 2 à 3 pages sur un profil riche.
- Boucle de régénération sur le nombre de pages du PDF : rejetée, trop lente et coûteuse en tokens.
- Ligne de synthèse pour les postes anciens : rejetée, elle échouerait au contrôle d'honnêteté (`cv_guards.py:142`) ; elle est remplacée par des entrées compactes.

## Surgical Scope
- **Files touched**:
  - `backend/app/llm/prompts/cv/tailor_prompt.md` (directives 4, 5, 6, 9)
  - `backend/app/services/cv_tailor.py` (`enforce_one_page_limits` + appel après le contrôle d'honnêteté)
  - `backend/tests/test_cv_tailor.py` (assertions L229-233 + nouveaux tests)
- **Files NOT touched**: `backend/app/models.py`, `backend/app/services/cv_templates.py` (import seul de `_most_recent_first`), `backend/app/services/cv_guards.py`, `backend/app/templates/cv/*`, `backend/app/routers/resumes.py`, tous les autres
- **Symbols replaced**: none
- **Symbols extended**: `generate_tailored_cv_content` (appel au post-traitement), `test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas`
- **Symbols created**: `enforce_one_page_limits`, `_merge_consecutive_stints`, constantes `MAX_EXPERIENCES`, `BULLETS_BY_RANK`, `MAX_TECHNOLOGIES`, `MAX_PROJECTS`, `MAX_SKILL_GROUPS`, `MAX_SKILLS_PER_GROUP`

## Definition of Done
- [x] Build passes: `cd backend && uv run python -m py_compile app/services/cv_tailor.py`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cv_tailor.py tests/test_cv_guards.py tests/test_cv_templates.py -v`
- [x] No dead code: n/a — none replaced
- [x] Type check: n/a — aucun type checker configuré côté backend
- [x] Post-traitement branché après le contrôle d'honnêteté : `grep -c 'enforce_one_page_limits' backend/app/services/cv_tailor.py` ≥ 2
- [x] Ordre identique au rendu (6 expériences en désordre → sortie triée comme `_most_recent_first`) : `test_enforce_sorts_like_renderer`
- [x] Plafonds de puces par rang (4 / 3 / 2) et entrées compactes à partir du rang 3 (0 puce, 0 technologie, titre, entreprise et dates conservés) : `test_enforce_caps_bullets_by_rank`
- [x] 6 expériences au maximum, les plus anciennes retirées : `test_enforce_drops_oldest_beyond_max`
- [x] Postes consécutifs chez le même employeur fusionnés (casse et espaces ignorés), avec la date de début du plus ancien, la date de fin, l'intitulé et le lieu du plus récent, les puces concaténées et les technologies dédoublonnées dans l'ordre : `test_enforce_merges_consecutive_same_employer`
- [x] Même employeur non consécutif (A, B, A) : pas de fusion : `test_enforce_keeps_non_consecutive_same_employer`
- [x] Au plus 6 `relevant_technologies` par expérience détaillée, 2 projets, 4 groupes de compétences et 8 compétences par groupe : `test_enforce_caps_projects_skills_technologies`
- [x] CV déjà sous les plafonds renvoyé inchangé (fixture `VALID_LLM_OUTPUT`) : `test_enforce_leaves_short_cv_unchanged`
- [x] Une page pour tous les profils : `grep -c 'deux pages' backend/app/llm/prompts/cv/tailor_prompt.md` → 0 et `grep -c 'Une page A4' backend/app/llm/prompts/cv/tailor_prompt.md` ≥ 1
- [x] Interdiction de supprimer une expérience retirée : `grep -c 'ne la supprime jamais' backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [x] Ordre antichronologique demandé au LLM : `grep -c 'antichronologique' backend/app/llm/prompts/cv/tailor_prompt.md` ≥ 1
- [x] Projets plafonnés dans le prompt : `grep -c '0 à 2 projets' backend/app/llm/prompts/cv/tailor_prompt.md` → 1
- [x] Prompt rendu sans `KeyError` ni accolade résiduelle : couvert par les tests `load_tailor_prompt` existants de `test_cv_tailor.py`
- [ ] Manual check: profil riche (≥ 5 expériences, dont 2 postes consécutifs dans la même entreprise) → générer un CV adapté → exporter le PDF dans les 4 templates (`classique`, `creatif`, `executive_minimalist`, `sidebar_elegance`) → chaque PDF tient sur 1 page, les deux postes apparaissent fusionnés en une seule entrée, les postes anciens en en-tête seul (observateur : utilisateur)

## Steps
- [x] Step 1: Réécrire les directives de `tailor_prompt.md` sans introduire d'accolade simple (`template.format`) :
  - **4** : « Classe les expériences dans l'ordre antichronologique (la plus récente d'abord). » Puces : 4 au maximum pour la plus récente, 3 pour la deuxième, 2 pour la troisième ; à partir de la quatrième, aucune puce ni outil (titre, entreprise et dates seuls). 6 expériences au maximum ; au-delà, omets les plus anciennes. Fusionne les postes consécutifs chez le même employeur en une seule entrée. Une puce = une ligne, environ 20 mots maximum. Supprimer « ne la supprime jamais » et les fourchettes « 4 à 5 » / « 1 à 2 ». Garder les exemples de métriques par métier et la phrase sur `relevant_technologies` (6 outils au maximum).
  - **5** : « 2 à 4 catégories, 8 compétences au maximum par catégorie ».
  - **6** : « 0 à 2 projets ».
  - **9** : « Une page A4 pour tous les profils. Pour tenir ce budget, raccourcis d'abord les expériences anciennes et les projets, jamais l'expérience la plus récente. » Supprimer « deux pages maximum ».
- [x] Step 2: Dans `cv_tailor.py`, importer `_most_recent_first` depuis `app.services.cv_templates` et ajouter `enforce_one_page_limits(cv: TailoredCVSchema) -> TailoredCVSchema` :
  1. trier les expériences avec `_most_recent_first([e.model_dump() for e in cv.experiences])` ;
  2. `_merge_consecutive_stints` : regrouper les voisins dont `company.strip().casefold()` est identique ; l'entrée fusionnée garde `title`, `location` et `end_date` du premier poste, `start_date` du dernier, les puces concaténées dans l'ordre et les technologies dédoublonnées en gardant l'ordre ;
  3. garder les `MAX_EXPERIENCES = 6` premières ;
  4. rang `i` < 3 : puces tronquées à `BULLETS_BY_RANK[i]` (4, 3, 2), technologies à `MAX_TECHNOLOGIES = 6` ; rang ≥ 3 : `bullet_points = []`, `relevant_technologies = []` ;
  5. `featured_projects[:MAX_PROJECTS]` (2), `prioritized_skills[:MAX_SKILL_GROUPS]` (4), puis `skills[:MAX_SKILLS_PER_GROUP]` (8) dans chaque groupe ;
  6. renvoyer `cv.model_copy(update={...})` sans muter l'objet reçu.
  Aucune troncature de texte dans le code : la longueur des puces reste une consigne du prompt. Dans `generate_tailored_cv_content`, remplacer `return tailored_cv` par `return enforce_one_page_limits(tailored_cv)`, après le contrôle d'honnêteté, qui reste fait sur la sortie brute du LLM.
- [x] Step 3: Dans `test_cv_tailor.py`, remplacer les assertions L229-231 (« 4 à 5 bullet points », « 1 à 2 bullet points », « 0 à 3 projets ») par `"antichronologique"` et `"0 à 2 projets"`, garder « CACES » et « Une page A4 », ajouter `assert "deux pages" not in prompt`. Ajouter les tests `test_enforce_*` nommés dans le DoD (fonction pure, sans LLM ni base de données).
- [x] Step 4: Lancer les commandes du DoD (build, tests, greps) et corriger jusqu'au vert.
- [x] Step 5 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the new symbols (`enforce_one_page_limits`, `_merge_consecutive_stints`, constantes `MAX_*` / `BULLETS_BY_RANK`). Confirm 0 orphans.

## Code Review
- Dead code removed: yes (0 orphans, all new symbols covered and tested)
- Build status: pass (py_compile exit 0)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-22T16:13Z | antigravity | preflight | done | py_compile exit 0, pytest 95 passed exit 0
- 2026-10-22T16:14Z | antigravity | step 1 | started
- 2026-10-22T16:15Z | antigravity | step 1 | done | prompt greps (deux pages: 0, Une page A4: 1, ne la supprime jamais: 0, antichronologique: 1, 0 à 2 projets: 1)
- 2026-10-22T16:16Z | antigravity | step 2 | started
- 2026-10-22T16:17Z | antigravity | step 2 | done | enforce_one_page_limits & _merge_consecutive_stints implemented and wired in cv_tailor.py
- 2026-10-22T16:19Z | antigravity | step 3 | started
- 2026-10-22T16:20Z | antigravity | step 3 | done | updated prompt assertions, added 7 test_enforce_* tests in test_cv_tailor.py
- 2026-10-22T16:21Z | antigravity | step 4 | started
- 2026-10-22T16:21Z | antigravity | step 4 | done | py_compile exit 0, pytest 102 passed exit 0, all 5 DoD greps confirmed
- 2026-10-22T16:22Z | antigravity | step 5 | done | teardown: 0 dead code, 0 orphans for new symbols

## Notes
- Revue du 2026-10-22 intégrée :
  - ligne de synthèse remplacée par des entrées compactes (contrôle d'honnêteté) ;
  - tri aligné sur le rendu (`_most_recent_first`) ;
  - règle de fusion explicite ;
  - point d'appel après `verify_cv_honesty` ;
  - assertions existantes L229-233 mises à jour ;
  - commandes en `uv run` ;
  - greps pour chaque exigence du prompt.
- Décisions par défaut, à confirmer avant exécution :
  - (a) entrées compactes plutôt que ligne de synthèse ;
  - (b) plafonds par position (le poste le plus récent est le plus détaillé), et non par pertinence : un poste ancien mais très pertinent passe en entrée compacte s'il est au rang 3 ou au-delà ;
  - (c) une page stricte pour tous les profils, y compris au-delà de 5 ans d'expérience.
- Les expériences retirées ou compactées ne disparaissent que du CV adapté. Le profil source n'est pas touché.
- `_most_recent_first` est privé à `cv_templates.py`. Il est importé tel quel pour garantir le même ordre qu'au rendu. Si cet import croisé gêne, le rendre public dans un autre plan.
