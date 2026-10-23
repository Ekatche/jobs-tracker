---
task: Corriger à la main les histoires STAR du kit d'entretien et confirmer avant de régénérer une section
description: interview prep manual edit STAR+R stories + confirm before regenerate — StarStoryCard.tsx edit mode (title, theme, target_requirement, situation, task, action, result, reflection, key_tags) saved via interviewPrepApi.update PUT /offers/{id}/interview-prep (endpoint existed, unused by UI); InterviewPrepTab.tsx handleSaveStory + window.confirm gate in handleGenerateModule for Régénérer and Tout générer overwriting sections; React Next.js frontend; backend generate_stories_endpoint clears stale mapped_story_id on anticipated_questions after story regeneration (FastAPI, MongoDB $set/$setOnInsert)
status: done
created: 2026-10-23
---

# Corriger les histoires STAR et confirmer avant de régénérer

## Context
- Existing code checked:
  - `frontend/src/components/interview/StarStoryCard.tsx` (170 l.) : carte en lecture seule. Props `story`, `index`. Bouton copier, repli de la carte. Aucune édition.
  - `frontend/src/components/interview/InterviewPrepTab.tsx` (409 l.) :
    - `handleGenerateModule` (L60) appelle directement les endpoints de génération, sans confirmation.
    - Les 4 boutons « Régénérer » (L288, L323, L358, L389) et « Tout générer » (L149) écrasent la section ou tout le kit.
    - Les compteurs dérivés `storiesCount`, `hasAudience`, `questionsCount`, `reverseCount`, `totalCompleted` sont calculés L115-119, après le retour anticipé `if (loading)`.
  - `frontend/src/lib/api.ts` : `interviewPrepApi.update(offerId, data)` existe (PUT) mais aucun composant ne l'appelle.
  - `frontend/src/types/interview.ts` : `StarRStory` (id, title, theme, target_requirement, situation, task, action, result, reflection, key_tags) et `UpdateInterviewPrepPayload`.
  - `backend/app/routers/interview_prep.py` L339-379 : `PUT /offers/{offer_id}/interview-prep` remplace `stories` si fourni et renvoie le document complet. Couvert par `test_update_and_export_interview_prep` (`backend/tests/test_interview_prep_api.py:91`). `StarRStory` côté backend (`backend/app/models.py:767`) : tous les champs texte sont des `str` obligatoires, `key_tags` est une liste.
  - Motif de confirmation existant : `confirm()` natif dans `ResumeCard.tsx:27` et `ResumePreviewModal.tsx:174` (« Régénérer une nouvelle version du CV… ? »).
  - Lien question → histoire (piste n°6, ajoutée à la demande de l'utilisateur) :
    - `generate_stories_endpoint` (`backend/app/routers/interview_prep.py:100`) écrase `stories` et laisse `anticipated_questions` intactes. Chaque histoire générée reçoit un uuid neuf (`StarRStory` construit sans `id`, `interview_prep_service.py:188`), donc tous les `mapped_story_id` existants deviennent des liens morts.
    - `generate_all_endpoint` (L279) génère les questions à partir des nouvelles histoires : pas de lien mort.
    - Le badge « Histoire STAR+R liée » (`AnticipatedQuestionsViewer.tsx:89`) et l'export Markdown (`interview_prep_service.py:506`) affichent ce lien mort sans le vérifier.
    - `$set` et `$setOnInsert` ne peuvent pas viser le même champ dans un même `update_one`.
- Fresh info looked up: n/a. Aucune nouvelle bibliothèque ; React state et `window.confirm` seulement.
- Git status checked: seul le renommage de l'archivage automatique de `20261022-fix-cover-letter-stale-selection` (et sa ligne dans `INDEX.md`) est en attente. Hors périmètre ; il partira avec le prochain commit.

## Simpler Alternative Considered
- Éditer chaque histoire dans une seule zone de texte libre : plus simple, mais casse la structure STAR qu'utilisent l'export Markdown et le renvoi des questions vers une histoire (`mapped_story_id`).
- Une fenêtre de confirmation sur mesure : rejeté, le projet utilise déjà `confirm()` natif pour la régénération des CV.
- Éditer les 4 sections : écarté par l'utilisateur, seules les histoires STAR sont concernées (ce sont les faits réels sur lesquels s'appuient les questions et le futur mode entraînement).
- Piste n°6, régénérer aussi les questions après les histoires : rejeté, cela coûte un appel au modèle de plus. Remettre à `null` les liens qui ne pointent vers aucune histoire actuelle ne coûte rien.
- Piste n°6, corriger côté frontend (masquer le badge si l'id est absent) : rejeté, l'export Markdown garderait le lien mort et la donnée resterait fausse.

## Surgical Scope
- **Files touched**:
  - `frontend/src/components/interview/StarStoryCard.tsx`
  - `frontend/src/components/interview/InterviewPrepTab.tsx`
  - `backend/app/routers/interview_prep.py` (piste n°6)
  - `backend/tests/test_interview_prep_api.py` (piste n°6)
- **Files NOT touched**: tous les autres, en particulier `AudiencePacksViewer.tsx`, `AnticipatedQuestionsViewer.tsx`, `ReverseQuestionsViewer.tsx`, `frontend/src/lib/api.ts`, `frontend/src/types/interview.ts`, `backend/app/services/interview_prep_service.py`, `backend/app/models.py` et les prompts.
- **Symbols replaced** (→ to delete before done): aucun.
- **Symbols extended** (→ keep):
  - `StarStoryCard` : prop optionnelle `onSave` et mode édition.
  - `InterviewPrepTab` : nouveau `handleSaveStory` ; `handleGenerateModule` reçoit la confirmation ; les compteurs dérivés remontent au-dessus de `handleGenerateModule`.
  - `generate_stories_endpoint` : remet à `null` les `mapped_story_id` des questions existantes qui ne pointent vers aucune des nouvelles histoires.

## Definition of Done
- [ ] Build passes: `cd frontend && npm run build` exit 0
- [ ] Tests pass: `cd backend && uv run pytest tests/test_interview_prep_api.py tests/test_interview_prep_service.py tests/test_interview_prep_models.py -q` exit 0 (contrat du PUT dont dépend l'interface, et nouveau test de la piste n°6). Le frontend n'a aucun lanceur de tests.
- [ ] Régénérer les histoires coupe les liens morts : `cd backend && uv run pytest tests/test_interview_prep_api.py -q -k stale_story_links` exit 0, avec 1 test passé (pas 0 sélectionné).
- [ ] No dead code: n/a — aucun symbole remplacé.
- [ ] Type check: `cd frontend && npx tsc --noEmit` exit 0
- [ ] Lint: `cd frontend && npm run lint` ne montre aucun avertissement sur `StarStoryCard.tsx` ni `InterviewPrepTab.tsx`.
- [ ] Les corrections sont enregistrées par le PUT existant : `grep -c 'interviewPrepApi.update' frontend/src/components/interview/InterviewPrepTab.tsx` vaut 1.
- [ ] Tous les champs d'une histoire sont modifiables : `grep -cE 'draft\.(title|theme|target_requirement|situation|task|action|result|reflection)' frontend/src/components/interview/StarStoryCard.tsx` vaut au moins 8, et `grep -c 'key_tags' frontend/src/components/interview/StarStoryCard.tsx` vaut au moins 2.
- [ ] Une seule garde de confirmation couvre les 4 « Régénérer » et « Tout générer » : `grep -c 'confirm(' frontend/src/components/interview/InterviewPrepTab.tsx` vaut 1.
- [ ] Seules les histoires sont modifiables : `git diff --quiet -- frontend/src/components/interview/AudiencePacksViewer.tsx frontend/src/components/interview/AnticipatedQuestionsViewer.tsx frontend/src/components/interview/ReverseQuestionsViewer.tsx` exit 0.
- [ ] Manual check: scénarios A à C de l'étape 5 (D et E facultatifs), tous conformes, sur http://localhost:3875.

## Steps
- [x] Step 1: Dans `StarStoryCard.tsx`, ajouter la prop optionnelle `onSave?: (story: StarRStory) => Promise<void>`.
  - Si `onSave` est fourni : un bouton « Modifier » (`FiEdit2`) dans l'en-tête, avec `stopPropagation` comme le bouton copier.
  - En mode édition, le corps de la carte devient un formulaire sur un brouillon `draft` (copie de `story`) :
    - champs texte pour `title`, `theme`, `target_requirement` ;
    - zones de texte pour `situation`, `task`, `action`, `result`, `reflection` ;
    - un champ `key_tags` saisi séparé par des virgules, découpé et nettoyé à l'enregistrement.
  - Boutons « Annuler » (abandonne le brouillon) et « Enregistrer » (appelle `onSave(draft)`, désactivé pendant l'enregistrement). Si l'enregistrement échoue, la carte reste en édition et affiche le message d'erreur.
  - Vérif : `cd frontend && npx tsc --noEmit` exit 0, et les deux `grep -c` de la DoD sur `StarStoryCard.tsx`.
- [x] Step 2: Dans `InterviewPrepTab.tsx`, ajouter `handleSaveStory(story)`.
  - Il remplace l'histoire de même `id` dans `prep.stories`, appelle `interviewPrepApi.update(offerId, { stories })` et met `prep` à jour avec la réponse.
  - Il laisse remonter l'erreur pour que la carte l'affiche.
  - Passer `onSave={handleSaveStory}` à chaque `StarStoryCard`.
  - Vérif : `cd frontend && npx tsc --noEmit` exit 0, et `grep -c 'interviewPrepApi.update'` vaut 1.
- [x] Step 3: Dans `InterviewPrepTab.tsx`, remonter les compteurs dérivés (L115-119) au-dessus de `handleGenerateModule`.
  - En tête de `handleGenerateModule`, si la section visée a déjà du contenu (n'importe quelle section pour `"all"`), demander `confirm()`. Sur « Annuler », sortir sans appel.
  - Message : « Régénérer cette section ? Son contenu actuel, y compris vos corrections, sera remplacé. » ; pour `"all"` : « Tout régénérer ? Le contenu actuel des 4 sections, y compris vos corrections, sera remplacé. »
  - Vérif : `cd frontend && npx tsc --noEmit` exit 0, et `grep -c 'confirm('` vaut 1.
- [x] Step 4: Piste n°6, dans `generate_stories_endpoint` (`backend/app/routers/interview_prep.py`).
  - Avant l'écriture, lire le kit existant avec `_get_prep_or_empty`. Reprendre ses `anticipated_questions` en remettant `mapped_story_id` à `None` quand il ne correspond à l'`id` d'aucune des nouvelles histoires. Les autres champs des questions restent inchangés.
  - Écrire ces questions dans le `$set`, et retirer `anticipated_questions` du `$setOnInsert` (MongoDB refuse le même champ dans les deux). Sans kit existant, la liste reste vide, comme avant.
  - Dans `backend/tests/test_interview_prep_api.py`, ajouter `test_generate_stories_clears_stale_story_links` :
    - créer un kit avec une histoire et deux questions : l'une liée à cette histoire, l'autre sans lien ;
    - régénérer les histoires avec `generate_star_stories` mocké ;
    - vérifier que la première question a `mapped_story_id` à `None` et garde son texte, et que les deux questions sont toujours là.
  - Vérif : `cd backend && uv run pytest tests/test_interview_prep_api.py -q -k stale_story_links` exit 0 (1 test passé).
- [x] Step 5: Contrôle manuel sur http://localhost:3875, sur une offre dont le kit contient déjà des histoires. Observateur : l'utilisateur (le Chrome piloté n'a pas de session connectée).
  - (A) Modifier le champ Résultat d'une histoire, enregistrer, recharger la page : la correction est toujours là, et elle apparaît dans « Copier .md ».
  - (B) Modifier un champ puis « Annuler » : l'histoire est inchangée.
  - (C) Cliquer « Régénérer » sur une section remplie, puis « Annuler » dans la confirmation : rien ne change, aucune génération ne part.
  - (D) Facultatif, coûte un appel au modèle : sur une section vide, « Générer » part sans confirmation.
  - (E) Facultatif, coûte un appel au modèle : régénérer les histoires d'un kit dont des questions portent le badge « Histoire STAR+R liée ». Après confirmation, plus aucun badge.
- [x] Step 6 (teardown): Aucun symbole remplacé, donc pas de recherche d'orphelins. Lancer `npm run lint` et `npm run build`, et le `git diff --quiet` de la DoD sur les trois visionneuses non touchées.

## Code Review
- Dead code removed: n/a, aucun symbole remplacé. `FiEdit2` et `StarRStory` importés et utilisés ; `npm run lint` ne signale rien sur `StarStoryCard.tsx` ni `InterviewPrepTab.tsx`.
- Build status: pass (`npm run build` exit 0, 2026-10-23T20:06Z)
- Type errors: none (`npx tsc --noEmit` exit 0)
- Unintended side effects: none. Diff relu en entier (`StarStoryCard.tsx`, `InterviewPrepTab.tsx`, `interview_prep.py`, test). Les 3 visionneuses sont intactes (`git diff --quiet` exit 0). Le même diff contient aussi le plan C (bouton Annuler) et le retrait de 2 imports inutilisés du fichier de test, fait à la clôture du plan C. Seul avertissement de lint : `ResumePreviewModal.tsx:122`, préexistant et hors périmètre.
- Security surface touched: no. Aucun code d'auth ni de secret. Les corrections passent par le PUT existant, déjà validé par Pydantic côté backend. Semgrep non lancé.
- Verdict: ✅ DONE

## Execution Log
- 2026-10-23T17:50Z | claude-code | preflight | done | baseline dans Notes ; 18 passed après démarrage de mongo_test
- 2026-10-23T17:50Z | claude-code | step 1 | started
- 2026-10-23T17:51Z | claude-code | step 1 | done | `npx tsc --noEmit` exit 0 ; grep draft.*=8, key_tags=3
- 2026-10-23T17:51Z | claude-code | step 2 | started
- 2026-10-23T17:52Z | claude-code | step 2 | done | `npx tsc --noEmit` exit 0 ; grep interviewPrepApi.update=1
- 2026-10-23T17:52Z | claude-code | step 3 | started
- 2026-10-23T17:52Z | claude-code | step 3 | done | `npx tsc --noEmit` exit 0 ; grep confirm(=1
- 2026-10-23T17:52Z | claude-code | step 4 | started
- 2026-10-23T17:54Z | claude-code | step 4 | done | `pytest -k stale_story_links` 1 passed exit 0 ; même test exit 1 avec le routeur de HEAD (contrôle rouge)
- 2026-10-23T17:55Z | claude-code | step 5 | started | stack locale démarrée (`docker compose up -d`), frontend 3875 → 200, backend /docs → 200 ; en attente de l'observation de l'utilisateur
- 2026-10-23T18:22Z | claude-code | step 5 | in progress | retour « pas d'option annuler » analysé (voir Notes) ; scénario C à refaire sur une section remplie
- 2026-10-23T18:26Z | claude-code | step 5 | in progress | confirmation affichée (utilisateur) ; E conforme (log POST generate/stories 18:24:51, 8/8 questions à `mapped_story_id` None) ; reste C (Annuler), A, B
- 2026-10-23T20:05Z | claude-code | step 5 | done | utilisateur : « tout est bon » — scénarios C (Annuler dans la confirmation), A (Résultat modifié, persistant après rechargement et dans « Copier .md ») et B (Annuler du formulaire) conformes ; E déjà vérifié en base à 18:26Z
- 2026-10-23T20:05Z | claude-code | step 6 | started
- 2026-10-23T20:07Z | claude-code | step 6 | done | `npm run lint` exit 0, 0 mention des 2 fichiers ; `npm run build` exit 0 ; `git diff --quiet` des 3 visionneuses exit 0
- 2026-10-23T20:07Z | claude-code | close | done | DoD frais : pytest (3 fichiers) 21 passed ; `-k stale_story_links` 1 passed ; tsc exit 0 ; greps update=1, confirm(=1, draft.*=8, key_tags=3 ; contrôle manuel A à C + E conformes. Test ajouté dépendant de mongo_test, comme tout le fichier (voir Notes du plan C)

## Notes
- 2026-10-23T17:16Z : plan écrit. Contexte : piste n°3 (« pouvoir corriger le kit ») de l'analyse du module de préparation d'entretien. Périmètre restreint aux histoires STAR par l'utilisateur. La piste n°1 (mode entraînement avec retour) suivra dans un plan à part.
- 2026-10-23T17:44Z : plan élargi à la piste n°6 (liens `mapped_story_id` morts après une régénération des histoires), à la demande de l'utilisateur (« ok pour les modifications hors plan »). Ajout de l'étape 4, de deux fichiers backend au périmètre et d'un item de DoD.
- 2026-10-23T17:50Z : conventions lues : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md`) et `.cursorrules`. Le nouveau test relève de « intégrité des données » dans les critères de pertinence de `CLAUDE.md`.
- Baseline (17:50Z) :
  - build exit 0 ; `tsc --noEmit` exit 0 ; lint exit 0, aucune ligne sur les deux fichiers du périmètre ;
  - pytest des 3 fichiers interview prep : 18 passed. Il a fallu démarrer Docker Desktop et `docker compose up -d mongo_test` (port 27018). Avant ça, les 4 tests API qui utilisent `test_db` échouaient sur `ServerSelectionTimeoutError: localhost:27018: Connection refused` ;
  - `-k stale_story_links` : 0 test collecté (test pas encore écrit) ;
  - greps : `interviewPrepApi.update`=0, `draft.*`=0, `key_tags`=1, `confirm(`=0 ; visionneuses sans diff (exit 0).
- Écart assumé avec la règle « pas de test qui a besoin d'une base vivante » : le nouveau test d'endpoint utilise `test_db` (Mongo réel), comme les 4 autres tests de `test_interview_prep_api.py`. C'est la convention du fichier, et le comportement à prouver est une écriture Mongo.
- Étape 4, 1er essai en échec : `ValidationError: 1 validation error for AnticipatedQuestion why_it_will_be_asked`. Le test ne fournissait pas ce champ obligatoire. Correction dans le test seul ; le code n'a pas changé.
- 2026-10-23T17:56Z : diff relu ligne à ligne, chaque ligne correspond aux étapes 1 à 4. `semgrep scan --config p/python --config p/secrets` sur `interview_prep.py` : 0 résultat, 0 erreur. `get_semgrep_sast_findings` n'a pas servi : il ne lit que les scans déjà envoyés sur la plateforme, pas le diff local.
- 2026-10-23T17:55Z, état de reprise : l'étape 5 est à `[~]` car elle attend le retour de l'utilisateur sur les scénarios A à C. Le code des étapes 1 à 4 est entièrement appliqué et vérifié. Prochaine action : noter le résultat de A à C, puis lancer l'étape 6 (teardown) et la clôture.
- 2026-10-23T18:21Z, retour de l'utilisateur pendant l'étape 5 : « quand je regenere, je n'ai pas d'option anuller ». Constat :
  - le chunk client servi (`.next/static/chunks/src_aecbfef2._.js`, compilé à 18:15) contient bien le message de confirmation : le navigateur a le nouveau code ;
  - le backend n'a reçu que deux POST : `generate/all` sur un kit vide (créé à 18:17:40, donc pas de confirmation, comme prévu) puis `generate/reverse-questions` (18:18:38) ;
  - le scénario C n'est donc pas encore observé sur une section déjà remplie. En attente : refaire C sur « Histoires STAR » (5 histoires), et préciser si « annuler » veut dire autre chose (arrêter une génération en cours, ou revenir à la version d'avant). Ces deux sens sont hors périmètre du plan.
- 2026-10-23T18:26Z, étape 5 en partie observée :
  - l'utilisateur confirme que la fenêtre de confirmation s'ouvre sur « Régénérer » des histoires ;
  - il a cliqué OK : `POST generate/stories` à 18:24:51 dans les logs du backend ;
  - scénario E vérifié en base, offre `6adba3ba9317b52b532e204d` : 4 nouvelles histoires, les 8 questions sont toujours là, `mapped_story_id` vaut `None` pour les 8, aucun lien mort.
  - Pas encore observé : C côté « Annuler » (aucune requête ne doit partir), ainsi que A et B.
- Reste hors périmètre : le prompt `anticipated_questions.md` autorise le modèle à renvoyer « le titre ou l'ID » de l'histoire. Un titre n'est donc pas forcément un id. Après une régénération des histoires, il est remis à `null` comme un id mort. Le prompt n'est pas modifié ici.
