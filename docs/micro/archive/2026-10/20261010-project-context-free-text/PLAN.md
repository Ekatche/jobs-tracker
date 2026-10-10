---
task: Contexte des projets en texte libre (profil + imports CV/site) au lieu d'une liste fermée de 6 valeurs
description: project context free text instead of closed enum (perso, client, recherche, consortium, associatif, evenement) — CandidateProject.context Literal → Optional[str] in models.py, remove normalize_project_context / PROJECT_CONTEXTS / _PROJECT_CONTEXT_SYNONYMS, remove _coerce_project_contexts (website collector) and project loop in cv_parser _clean_parsed_cv, LLM prompts ask a short free label, merge.py drops "perso" fallback, CandidateProfileSection.tsx select dropdown → text input with legacy slug → label display (evenement → Événement), types/coverLetter.ts; pytest test_project_context test_profile_collectors test_profile_endpoints test_cv_vlm_parser
status: done
created: 2026-10-10
---

# Contexte des projets en texte libre

## Context
- Existing code checked:
  - `backend/app/models.py:515-550` — `PROJECT_CONTEXTS`, `_PROJECT_CONTEXT_SYNONYMS`, `normalize_project_context` (repli "perso"), `CandidateProject.context: Literal[6 valeurs] = "perso"` + `field_validator` qui normalise.
  - `backend/app/services/cv_parser.py:11,139-143` (normalisation dans `_clean_parsed_cv`), prompts `:51`, `:223`, `:331` qui énumèrent les 6 valeurs.
  - `backend/app/services/profile/collectors/website.py:27,49-61,317` (`_coerce_project_contexts`), prompt `:215` « une valeur EXACTE parmi ».
  - `backend/app/services/profile/merge.py:324` — repli `or "perso"`.
  - `backend/app/services/profile/collectors/github.py:110` — `"context": "perso"` (laissé tel quel : affiché "Perso" par la table de libellés côté frontend).
  - `backend/app/services/profile/context.py:48` — passe `context` brut au LLM (texte libre OK, pas touché).
  - Stockage : `_store_source` (`backend/app/routers/cover_letters.py:295`) valide avec `CandidateProfile.model_validate` mais écrit le dict brut ; `GET /profile/candidate` renvoie le document brut. Le validateur Pydantic ne réécrit donc jamais les données stockées : la conversion des anciens codes en libellés doit se faire à l'affichage (frontend).
  - Frontend : `frontend/src/components/profile/CandidateProfileSection.tsx:43-50` (`PROJECT_CONTEXT_OPTIONS`), `:279` (défaut "perso"), `:825` (badge), `:1436-1447` (`<select>`) ; `frontend/src/types/coverLetter.ts:22`.
  - Tests liés : `test_project_context.py`, `test_profile_collectors.py:239,270,635`, `test_profile_endpoints.py:185`, `test_cv_vlm_parser.py:104`. `test_profile_merge.py` et `test_cover_letter_models.py` passent "perso" explicitement, ils ne dépendent pas du repli.
  - Baseline : `uv run pytest tests/test_project_context.py tests/test_profile_collectors.py tests/test_profile_endpoints.py tests/test_cv_vlm_parser.py tests/test_profile_merge.py tests/test_cover_letter_models.py -q`, 115 passed.
- Fresh info looked up: n/a (Pydantic `field_validator` et `<input>` React déjà utilisés dans le repo)
- Git status checked: renommages d'archive du hook micro-dev (`docs/micro/INDEX.md`, `20261010-cv-summary-grounded-in-experience`) non commités, hors périmètre, laissés tels quels.

Décisions de l'utilisateur (2026-10-10) : texte libre **partout** (saisie manuelle ET imports CV/site) ; anciens codes **affichés en libellé propre** (sans migration de la base) ; **champ texte simple**, sans suggestions.

## Simpler Alternative Considered
Frontend seul (`<select>` → `<input>`) : la sauvegarde manuelle passerait déjà, puisque le validateur normalise une copie et que le dict brut est stocké. Mais les imports CV/site continueraient d'écraser "stage" ou "freelance" en "perso", et le `Literal` resterait un mensonge sur le modèle. L'utilisateur a choisi « partout ».

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/services/cv_parser.py`
  - `backend/app/services/profile/collectors/website.py`
  - `backend/app/services/profile/merge.py`
  - `frontend/src/components/profile/CandidateProfileSection.tsx`
  - `frontend/src/types/coverLetter.ts`
  - `backend/tests/test_project_context.py`
  - `backend/tests/test_profile_collectors.py`
  - `backend/tests/test_profile_endpoints.py`
  - `backend/tests/test_cv_vlm_parser.py`
- **Files NOT touched**: all others (notamment `github.py`, `profile/context.py`, `routers/cover_letters.py`, templates CV)
- **Symbols replaced** (→ to delete before done): `PROJECT_CONTEXTS`, `_PROJECT_CONTEXT_SYNONYMS`, `normalize_project_context`, `CandidateProject.normalize_context` (remplacé par un validateur de nettoyage), `_coerce_project_contexts`, `PROJECT_CONTEXT_OPTIONS`, tests `test_collect_website_keeps_valid_project_context_untouched`, `test_coerce_project_contexts_maps_synonyms_before_fallback`, `test_clean_parsed_cv_maps_new_project_contexts`
- **Symbols extended** (→ keep): `CandidateProject`, `_clean_parsed_cv`, `collect_website`, `_merge_projects`, `CandidateProfileSection`, `CandidateProject` (TS)

## Definition of Done
- [x] Build passes: `cd frontend && npm run build`
- [x] Tests pass (ciblés): `cd backend && uv run pytest tests/test_project_context.py tests/test_profile_collectors.py tests/test_profile_endpoints.py tests/test_cv_vlm_parser.py tests/test_profile_merge.py tests/test_cover_letter_models.py -q`
- [x] Tests pass (suite complète, aucune autre référence cassée) : `cd backend && uv run pytest -q`
- [x] No dead code: `git grep -n -E 'normalize_project_context|PROJECT_CONTEXTS|_PROJECT_CONTEXT_SYNONYMS|_coerce_project_contexts|PROJECT_CONTEXT_OPTIONS' -- backend frontend/src` renvoie 0 ligne
- [x] Lint backend : `cd backend && uv run ruff check app/models.py app/services/cv_parser.py app/services/profile/collectors/website.py app/services/profile/merge.py tests/test_project_context.py tests/test_profile_collectors.py tests/test_profile_endpoints.py tests/test_cv_vlm_parser.py`
- [x] Type check: `cd frontend && npx tsc --noEmit`
- [x] Plus de dropdown pour le contexte : `grep -A3 '>Contexte</label>' frontend/src/components/profile/CandidateProfileSection.tsx | grep -c '<select'` donne 0, et `... | grep -c 'type="text"'` donne 1
- [x] Les imports n'imposent plus de liste : `git grep -n -E 'perso \| client|perso, client|"perso", "client"|valeur EXACTE' -- backend/app` renvoie 0 ligne
- [x] Plus de repli "perso" au merge : `grep -c 'or "perso"' backend/app/services/profile/merge.py` donne 0
- [x] Anciens codes affichés en libellé : `grep -c 'evenement: "Événement"' frontend/src/components/profile/CandidateProfileSection.tsx` donne 1, et la même fonction de libellé sert au badge et au champ (`grep -c 'projectContextLabel(proj.context)' ...` ≥ 2)
- [x] Texte libre accepté de bout en bout via l'API : couvert par `test_profile_endpoints.py` (import site avec "stage" → 200 et "stage" conservé)
- [ ] Manual check : profil, section Projets → le champ Contexte est un champ texte ; un projet "client" s'affiche "Client" ; saisir "Stage", enregistrer, recharger : "Stage" reste (observateur : utilisateur, après déploiement)

## Steps
- [x] Step 1 (backend modèle) : dans `models.py`, supprimer `PROJECT_CONTEXTS`, `_PROJECT_CONTEXT_SYNONYMS`, `normalize_project_context` ; `CandidateProject.context: Optional[str] = None` ; remplacer `normalize_context` par un validateur `mode="before"` qui renvoie `v.strip() or None` pour une chaîne et `None` sinon (garde la résilience aux sorties LLM non-chaîne, qui sinon donneraient un 502 à l'import). Réécrire `test_project_context.py` : texte libre conservé (et nettoyé des espaces), chaîne vide → None, non-chaîne → None, défaut None.
- [x] Step 2 (imports) : `cv_parser.py`, retirer l'import et la boucle projets de `_clean_parsed_cv`, et reformuler les 3 mentions du prompt en « libellé court en texte libre, fidèle au CV (ex : Perso, Client, Stage, Associatif) ». `website.py`, supprimer `_coerce_project_contexts`, son appel et son import, et reformuler le prompt `:215` de la même façon. Tests : `test_cv_vlm_parser.py`, supprimer `test_clean_parsed_cv_maps_new_project_contexts`. `test_profile_collectors.py` : réécrire le test `:239` pour vérifier que "freelance" est conservé tel quel, supprimer le test `:270` (devenu doublon) et le test `:635`, ainsi que l'import de `_coerce_project_contexts`. `test_profile_endpoints.py:185` : réécrire sans `_coerce_project_contexts` et vérifier que "stage" traverse `_store_source` (200 et "stage" renvoyé).
- [x] Step 3 (merge) : `merge.py:324`, retirer le repli `or "perso"`. Lancer les tests ciblés backend et ruff.
- [x] Step 4 (frontend) : `CandidateProfileSection.tsx`, remplacer `PROJECT_CONTEXT_OPTIONS` par une table `LEGACY_PROJECT_CONTEXT_LABELS` (anciens codes vers libellés) et une fonction `projectContextLabel(context)` qui renvoie le libellé, sinon la valeur telle quelle, sinon "". Badge `:825` → `projectContextLabel(proj.context)`. `<select>` → `<input type="text" value={projectContextLabel(proj.context)} placeholder="ex: Client, Perso, Stage, Associatif">`. Défaut de `handleAddProject` → `context: ""`. Dans `coverLetter.ts:22`, `context?: string | null`. Lancer `npx tsc --noEmit` puis `npm run build`.
- [x] Step 5 (teardown) : orphan scan `git grep` borné aux symboles remplacés (DoD « No dead code ») → 0 ; suite backend complète ; vérifier les greps du DoD.

## Code Review
- Dead code removed: yes. Les 6 symboles et les 3 tests remplacés sont absents : `git grep` 0 ligne, `callers_of` du graphe « not found ».
- Build status: pass. `npm run build` exit 0 ; pytest ciblé 101 passed ; suite complète (sans `test_users.py`) : 6 failed / 7 errors, identiques à la baseline (`diff` vide). 825 passed contre 839 : −14 tests supprimés ou fusionnés par ce plan.
- Type errors: none (`npx tsc --noEmit` exit 0).
- Unintended side effects: none dans le code. Quatre points à connaître :
  1. Un projet sans contexte n'a plus de valeur par défaut : `context` est `None` au lieu de "perso", et le badge ne s'affiche pas.
  2. `github.py` écrit toujours "perso", affiché « Perso ».
  3. Dans le champ texte, taper exactement un ancien code (ex. "client") l'affiche avec son libellé (« Client »).
  4. Une assertion de `test_cv_vlm_parser.py` est adaptée, voir Notes.
- Security surface touched: yes, validation d'entrée (`CandidateProject`). semgrep `p/default` + `p/secrets` sur les 6 fichiers source : pass, 0 finding. Un avertissement de parsing partiel concerne des lignes TSX non touchées.
- Verdict: ✅ DONE. Tous les items du DoD passent, sauf la vérification manuelle, à faire par l'utilisateur après déploiement.

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-10T09:57Z | claude-code | preflight | done | tsc exit 0 ; npm run build exit 0 ; pytest ciblé 115 passed ; ruff 2 erreurs préexistantes ; suite complète `tests/` en cours (test_users.py bloque, exclu)
- 2026-10-10T09:57Z | claude-code | step 1 | started
- 2026-10-10T10:03Z | claude-code | step 1 | done | `uv run pytest tests/test_project_context.py tests/test_cover_letter_models.py -q` 15 passed ; `git grep` des symboles retirés dans backend/app : 0 ligne
- 2026-10-10T10:03Z | claude-code | step 2 | started
- 2026-10-10T10:04Z | claude-code | step 2 | done | pytest ciblé 6 fichiers 101 passed (exit 0) ; 1er run : 1 échec `test_parse_cv_with_llm_prompt_routes_habilitations_and_mobility` corrigé, voir Notes
- 2026-10-10T10:05Z | claude-code | step 3 | started
- 2026-10-10T10:05Z | claude-code | step 3 | done | pytest ciblé 101 passed (exit 0) ; ruff : 2 erreurs, les 2 préexistantes (E741 `cv_parser.py:157`, décalée depuis 164 ; F401 `io`), aucune nouvelle
- 2026-10-10T10:06Z | claude-code | step 4 | started
- 2026-10-10T10:07Z | claude-code | step 4 | done | `npx tsc --noEmit` exit 0 ; `npm run build` exit 0 (« Compiled successfully » ; 2 warnings `exhaustive-deps` préexistants, useEffect non touchés)
- 2026-10-10T10:08Z | claude-code | step 5 | started
- 2026-10-10T10:17Z | claude-code | step 5 | done | orphan scan `git grep` 0 ligne ; greps du DoD conformes ; suite complète 6 failed / 825 passed / 7 errors, liste d'échecs identique à la baseline (`diff` exit 0)
- 2026-10-10T10:18Z | claude-code | close-out | done | DoD repassé en entier : build exit 0, pytest ciblé 101 passed, dead code 0, ruff = 2 erreurs préexistantes, tsc exit 0, select=0/text=1, prompts 0, repli 0, libellé 1/helper 2 ; semgrep 0 finding ; vérification manuelle laissée à l'utilisateur

## Notes
- 10 fichiers, au-dessus de la fourchette micro (1-5), mais le résultat est connu et la majorité des modifications sont des suppressions (normalisation, coercition, tests associés).
- Validation d'entrée touchée (validateur Pydantic, coercition des sorties LLM) : ce n'est pas un chemin d'injection, mais semgrep (sast + secrets) sera lancé avant le verdict, par prudence.
- Les données existantes ne sont pas migrées : les anciens codes restent en base et sont affichés en libellé côté frontend. Dès qu'un projet est édité, le libellé (ou la nouvelle saisie) est sauvegardé.
- Le déploiement en production n'est pas inclus dans le plan, il reste à la main de l'utilisateur.
- Conventions lues (Phase 3) : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`) et `.cursorrules`, qui imposent d'interroger code-review-graph `tests_for` avant de supprimer un test. Fait : `tests_for` sur `normalize_project_context` et `_coerce_project_contexts` confirme la liste de tests du plan.
- Arbre de travail : une autre session travaille en parallèle (`backend/tests/test_cover_letter_crew.py`, `backend/tests/test_letter_guards.py` modifiés, plan `20261010-letter-projects-and-natural-job-title/` non suivi). C'est hors du périmètre de ce plan, je n'y touche pas.
- Baseline DoD (avant modification) : `tsc --noEmit` exit 0 ; `npm run build` exit 0 ; pytest ciblé 115 passed ; dead code 28 lignes ; `<select>` 1 / `type="text"` 0 ; prompts énumérant les valeurs : 6 lignes ; repli merge : 1 ; libellé legacy 0 / helper 0.
- Baseline ruff : 2 erreurs déjà présentes, hors de ce changement : `app/services/cv_parser.py:164` E741 (`l`) et `tests/test_cv_vlm_parser.py:1` F401 (`io`). Elles ne sont pas corrigées ici (changement chirurgical). Critère retenu pour le DoD ruff : aucune erreur nouvelle, la sortie se limite à ces 2 erreurs.
- Suite complète : `uv run pytest -q` lancé depuis `backend/` ramasse aussi `app/tasks/tests/test_job_crawler_wf.py`, un workflow réel qui bloque ; `tests/test_users.py` bloque aussi (4e test). Commande retenue pour le DoD « suite complète » : `cd backend && uv run pytest tests -q --ignore=tests/test_users.py`, comparée à la baseline (échecs préexistants, dont certains viennent peut-être de la session parallèle).
- Step 1, échec au premier essai : `ImportError: cannot import name 'normalize_project_context'`. Le `conftest` charge toute l'app, donc `cv_parser` et `website` cassaient la collecte. Correctif dans l'étape, au titre du Dead Code Gate : retrait de l'import et de la boucle projets de `_clean_parsed_cv`, de `_coerce_project_contexts`, de son appel et de son import, soit la partie code de l'étape 2. L'étape 2 garde les prompts et les tests.
- Step 2, échec au premier essai : `tests/test_cv_vlm_parser.py::test_parse_cv_with_llm_prompt_routes_habilitations_and_mobility` vérifiait `"associatif" in prompt`, c'est-à-dire que le prompt énumérait la valeur d'énum. Le prompt écrit maintenant « Associatif » comme exemple de texte libre. Correctif : l'assertion vérifie `"texte libre" in prompt`, l'invariant qui compte désormais. Le test `test_profile_endpoints.py` vérifie maintenant que « stage » traverse `_store_source` (200).
- Baseline suite complète (`uv run pytest tests -q -rfE -p no:cacheprovider --ignore=tests/test_users.py`, lancée avant les modifications) : 6 failed, 839 passed, 7 errors. Échecs préexistants, hors périmètre : ERROR `test_applications.py` (2 : `test_create_and_get_application_with_offer_id`, `test_update_description_never_overwrites_shared_offer`), ERROR `test_tasks.py` (5), FAILED `test_interview_prep_api.py` (4), `test_resumes_api.py::test_generate_resume_passes_evaluation_stored_with_string_ids`, `test_usage_tier_api.py::test_update_user_tier`. Liste dans le scratchpad de session (`baseline-failures.txt`). Critère step 5 : même liste d'échecs, aucun nouveau.
- Step 5 : suite complète terminée, échecs identiques à la baseline. La commande `uv run pytest -q` du DoD est remplacée par `uv run pytest tests -q --ignore=tests/test_users.py` (voir plus haut : blocages préexistants).
- Tests modifiés par ce plan : tous mockés (DB en mémoire `profile_db`, `collect_website` ou `extract` factices, IP littérale). Ils passent sans service externe : les tests qui ont besoin de Mongo (`test_applications`, `test_tasks`) sont en ERROR dans le même run, alors que ceux-ci passent.
- Reste à faire (utilisateur) : commit, déploiement, puis la vérification manuelle du DoD en production.
