---
task: Mode entraînement du kit d'entretien, partie frontend — panneau « S'entraîner » sous chaque question anticipée, retour noté et historique
description: interview prep practice mode frontend — PracticePanel.tsx (new React Next.js component, textarea answer maxLength 6000, submit to interviewPrepApi.practice POST /offers/{id}/interview-prep/practice, shows 4 criteria scores structure / quantified_result / offer_fit / coverage, overall_score /5, missing points, improved_answer with [à chiffrer] placeholders, per-question attempt history with progression), AnticipatedQuestionsViewer.tsx S'entraîner toggle per question card, InterviewPrepTab.tsx passes offerId practice_attempts setPrep and regenerate confirm warns practice history will be erased, types interview.ts PracticeCriterion PracticeAttempt InterviewPrep.practice_attempts, api.ts interviewPrepApi.practice
status: done
created: 2026-10-23
---

# Mode entraînement — frontend : panneau « S'entraîner »

## Context
- Existing code checked :
  - `frontend/src/components/interview/AnticipatedQuestionsViewer.tsx` (129 lignes) : prop unique `questions`, une carte par question (catégorie, badge « Histoire STAR+R liée », pourquoi, points clés), aucune action.
  - `frontend/src/components/interview/InterviewPrepTab.tsx` l. 431 : `<AnticipatedQuestionsViewer questions={prep!.anticipated_questions} />`. Elle tient `prep` / `setPrep` et `offerId`. Gestion d'erreur l. 102-107 : `err instanceof Error ? err.message : …`.
  - `frontend/src/lib/api.ts` l. 898-925 : `interviewPrepApi` utilise `fetchApi<InterviewPrep>(url, method, body)`.
  - `frontend/src/types/interview.ts` : `AnticipatedQuestion`, `InterviewPrep` (sans historique).
  - Pas de lanceur de tests frontend (`package.json` : `build`, `lint` seulement).
- Fresh info looked up : n/a, aucune nouvelle librairie (React, react-icons `fi` et Tailwind sont déjà utilisés).
- Git status checked : `api.ts` et `InterviewPrepTab.tsx` portent les changements non commités des plans A et C de cette session (clos, connus). `types/interview.ts` et `AnticipatedQuestionsViewer.tsx` sont propres.
- Dépend du plan `20261023-interview-practice-feedback-api` (endpoint et champ `practice_attempts`), à exécuter d'abord.

## Simpler Alternative Considered
- Mettre le formulaire directement dans `AnticipatedQuestionsViewer` sans nouveau composant : moins de fichiers, mais la visionneuse passerait d'environ 130 à plus de 300 lignes, avec l'état de chaque panneau mélangé au filtre. Un composant `PracticePanel` garde l'état (brouillon, envoi, erreur, tentative affichée) local à une question.
- Pas d'historique visible, seulement la dernière note : ne répond pas à « suivre la progression ». Écarté.

## Surgical Scope
- **Files touched**:
  - `frontend/src/types/interview.ts`
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/interview/PracticePanel.tsx` (nouveau)
  - `frontend/src/components/interview/AnticipatedQuestionsViewer.tsx`
  - `frontend/src/components/interview/InterviewPrepTab.tsx`
- **Files NOT touched**: tout le reste : backend, `StarStoryCard.tsx`, `AudiencePacksViewer.tsx`, `ReverseQuestionsViewer.tsx`.
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `InterviewPrep` (TS, + `practice_attempts?`)
  - `interviewPrepApi` (+ `practice`)
  - `AnticipatedQuestionsViewerProps` (+ `offerId`, `attempts`, `onPrepUpdated`)
  - `handleGenerateModule` (message de confirmation)
  - Nouveaux : `PracticeCriterion`, `PracticeAttempt`, `PracticePanel`

## Definition of Done
- [x] Type check : `cd frontend && npx tsc --noEmit` (exit 0)
- [x] Lint : `cd frontend && npx eslint src/components/interview/PracticePanel.tsx src/components/interview/AnticipatedQuestionsViewer.tsx src/components/interview/InterviewPrepTab.tsx src/lib/api.ts src/types/interview.ts` (exit 0)
- [x] Build : `cd frontend && npm run build` (exit 0)
- [x] Tests : n/a, aucun lanceur de tests frontend dans le projet. La logique (notes, moyenne, garde des chiffres) est testée côté backend.
- [x] Appel API branché : `grep -c "interview-prep/practice" frontend/src/lib/api.ts` vaut 1.
- [x] Historique typé : `grep -c "practice_attempts" frontend/src/types/interview.ts` vaut 1.
- [x] Panneau branché dans la visionneuse : `grep -c "<PracticePanel" frontend/src/components/interview/AnticipatedQuestionsViewer.tsx` vaut 1.
- [x] Saisie plafonnée comme côté serveur : `grep -c "maxLength={6000}" frontend/src/components/interview/PracticePanel.tsx` vaut 1.
- [x] Les 4 critères ont un libellé français : `grep -cE "structure|quantified_result|offer_fit|coverage" frontend/src/components/interview/PracticePanel.tsx` ≥ 4.
- [x] Effacement annoncé avant régénération : `grep -c "historique d'entraînement" frontend/src/components/interview/InterviewPrepTab.tsx` ≥ 1.
- [x] No dead code : n/a, aucun symbole remplacé. eslint ne signale aucun import inutilisé.
- [x] Manual check (observateur : l'utilisateur, stack locale, une offre dont le kit a des questions) :
  1. Section « Questions », bouton « S'entraîner » sur une question liée à une histoire. Le panneau s'ouvre avec une zone de texte et un compteur sur 6000.
  2. Écrire une réponse courte sans chiffre, puis « Obtenir un retour ». Pendant l'analyse, le bouton est désactivé. Ensuite s'affichent la note globale sur 5, les 4 critères commentés, les manques et une version retravaillée qui contient `[à chiffrer]` au lieu de chiffres inventés.
  3. Seconde tentative, enrichie : l'historique de la question montre 2 essais datés, avec l'évolution de la note. Un clic sur l'ancien essai réaffiche son retour.
  4. Recharger la page : l'historique est toujours là.
  5. Coût : une ligne `interview_prep` / `practice` par tentative dans le suivi d'usage, soit 1 appel LLM par réponse.
  6. « Régénérer » les questions : la confirmation annonce que l'historique d'entraînement (2 essais) sera effacé. Si on annule, rien ne change.

## Steps
- [x] Step 1 : types et API.
  - Dans `interview.ts` : `PracticeCriterion { key; score; comment }`, `PracticeAttempt { id; question_id; question; answer; criteria; overall_score; missing; improved_answer; created_at }`, et `practice_attempts?: PracticeAttempt[]` dans `InterviewPrep`.
  - Dans `api.ts` : `practice(offerId, questionId, answer)`, qui fait un POST `{ question_id, answer }` et renvoie `InterviewPrep`.
  - Vérif : `npx tsc --noEmit` et les 2 `grep -c`.
- [x] Step 2 : `PracticePanel.tsx`.
  - Props : `offerId`, `question`, `attempts` (celles de cette question), `onPrepUpdated`.
  - État local : brouillon, envoi en cours, erreur, tentative affichée (la plus récente par défaut).
  - Zone de texte (`maxLength={6000}`, compteur), bouton « Obtenir un retour » désactivé si le brouillon est vide ou pendant l'envoi.
  - Retour affiché :
    - note globale sur 5 ;
    - les 4 critères avec un libellé français (Structure, Résultat chiffré, Adéquation à l'offre, Points clés et histoire), une note et un commentaire ;
    - la liste « Ce qui manque » ;
    - le bloc « Version retravaillée ».
  - Historique : liste datée des essais avec la note, et l'écart avec l'essai précédent ; un clic affiche l'essai.
  - Erreur : message du serveur, même forme que dans `InterviewPrepTab`.
  - Style : cohérent avec la carte (slate et indigo, icônes `fi`).
  - Vérif : `npx tsc --noEmit`, puis `npx eslint` sur le fichier et les 2 `grep -c`.
- [x] Step 3 : `AnticipatedQuestionsViewer.tsx`.
  - Nouvelles props `offerId`, `attempts`, `onPrepUpdated`.
  - Dans chaque carte, un bouton « S'entraîner », avec le nombre d'essais et la dernière note s'il y en a. Il ouvre ou ferme le `PracticePanel` de la question.
  - Le panneau reste monté et masqué quand il est fermé, pour ne pas perdre le brouillon.
  - Vérif : `npx tsc --noEmit` et `grep -c "<PracticePanel"`.
- [x] Step 4 : `InterviewPrepTab.tsx`.
  - Passer `offerId`, `attempts={prep!.practice_attempts ?? []}` et `onPrepUpdated={setPrep}` à la visionneuse.
  - Dans `handleGenerateModule`, pour `questions` et `all` avec des essais existants, la confirmation ajoute : « Votre historique d'entraînement (N essais) sera effacé. »
  - Vérif : `npx tsc --noEmit`, `grep -c "historique d'entraînement"`, `npx eslint` sur les 5 fichiers, puis `npm run build`.
- [x] Step 5 (teardown) : aucun symbole remplacé, donc pas de scan d'orphelins. Relancer tout le DoD, relire le diff ligne à ligne, puis faire dérouler le scénario manuel par l'utilisateur.

## Code Review
- Dead code removed: n/a, aucun symbole remplacé. eslint ne signale aucun import inutilisé sur les 5 fichiers.
- Build status: pass. `npm run build` exit 0, avec 2 warnings `react-hooks/exhaustive-deps` préexistants hors périmètre (`CandidateProfileSection.tsx:380`, `ResumePreviewModal.tsx:122`). eslint exit 0 sur les 5 fichiers. Les 7 `grep -c` du DoD sont conformes.
- Type errors: aucune au final. Entre les étapes 3 et 4, `TS2739` à l'appel de la visionneuse, attendu, voir Notes.
- Unintended side effects: aucun. La confirmation « Régénérer » ne change que si des essais existent, pour `questions` et `all`. Les autres hunks d'`InterviewPrepTab.tsx` et d'`api.ts` viennent des plans A et C, déjà clos.
- Security surface touched: non, l'affichage passe par du texte React échappé, sans `dangerouslySetInnerHTML`. La validation reste côté serveur.
- Verdict: ✅ DONE. DoD automatisé au vert (2026-10-23T20:38Z), scénario manuel validé par l'utilisateur (2026-10-23T20:44Z).

## Execution Log
- 2026-10-23T20:31Z | claude-code | preflight | done | baseline logged in Notes
- 2026-10-23T20:31Z | claude-code | step 1 | started
- 2026-10-23T20:32Z | claude-code | step 1 | done | `npx tsc --noEmit` exit 0 ; `grep -c "interview-prep/practice" api.ts` = 1 ; `grep -c "practice_attempts" interview.ts` = 1
- 2026-10-23T20:32Z | claude-code | step 2 | started
- 2026-10-23T20:35Z | claude-code | step 2 | done | `npx tsc --noEmit` exit 0 ; `npx eslint PracticePanel.tsx` exit 0 ; `grep -c "maxLength={6000}"` = 1 ; grep critères = 4 ; `dangerouslySetInnerHTML` = 0
- 2026-10-23T20:35Z | claude-code | step 3 | started
- 2026-10-23T20:36Z | claude-code | step 4 | started | requis pour la vérif tsc de l'étape 3, voir Notes
- 2026-10-23T20:36Z | claude-code | step 3 | done | `npx tsc --noEmit` exit 0 (après étape 4) ; `grep -c "<PracticePanel"` = 1
- 2026-10-23T20:36Z | claude-code | step 4 | done | `npx tsc --noEmit` exit 0 ; `grep -c "historique d'entraînement"` = 1 ; `npx eslint` 5 fichiers exit 0 ; `npm run build` exit 0 (2 warnings exhaustive-deps préexistants hors périmètre)
- 2026-10-23T20:36Z | claude-code | step 5 | started
- 2026-10-23T20:38Z | claude-code | step 5 | dod-rerun | tsc 0, eslint 0, build 0 ; api=1 types=1 panel=1 max=1 crit=4 hist=1 html=0 ; diff relu
- 2026-10-23T20:38Z | claude-code | step 5 | waiting | scénario manuel en attente (observateur : l'utilisateur)
- 2026-10-23T20:44Z | claude-code | step 5 | done | scénario manuel validé par l'utilisateur (« ok pour cette etape ») ; `npx tsc --noEmit` exit 0, code inchangé depuis la passe DoD
- 2026-10-23T20:44Z | claude-code | close | done | status: done

## Notes
- Clos le 2026-10-23T20:44Z : scénario manuel validé par l'utilisateur.
- Relecture du diff (étape 5) : j'ai ajouté un `<details>` « Votre réponse » dans `PracticePanel` pour qu'un ancien essai réaffiche aussi le texte soumis (« un clic affiche l'essai »). Le DoD a été relancé ensuite.
- Limite connue : changer le filtre (Toutes, Comportementales, Techniques) démonte les cartes masquées, et leur brouillon non envoyé est perdu. Les essais envoyés ne sont pas touchés.
- Step 3 : sa vérif `tsc` ne pouvait pas passer seule. Le seul échec était `InterviewPrepTab.tsx(431,16): error TS2739: ... missing ... offerId, attempts, onPrepUpdated`, c'est-à-dire l'appel modifié par l'étape 4. J'ai donc fait l'étape 4, puis vérifié les deux. Défaut d'ordre du plan, sans changement de périmètre.
- Step 2 : `created_at` est relu sans fuseau (client Motor sans `tz_aware`, `backend/app/database.py:50`). `PracticePanel` ajoute le « Z » manquant avant d'afficher l'heure locale.
- Choix de construction (les miens) :
  - Le panneau est inline sous chaque question : on reste dans l'onglet, sans fenêtre modale.
  - Pas de bouton « Annuler » : l'appel dure quelques secondes, et une tentative payée est gardée côté serveur.
  - L'historique est affiché par question (`question_id`).
- Décision de l'utilisateur (23/10) : pas d'essai orphelin. Le backend efface les essais d'une question disparue, et la confirmation de régénération le dit avant.
- Conventions lues : `CLAUDE.md` racine (graphe, directives de tests) ; aucun `CLAUDE.md`, `AGENTS.md` ni `GEMINI.md` dans `frontend/`. Rien ne contredit le plan.
- Le plan backend `20261023-interview-practice-feedback-api` est clos (`status: done`) : l'endpoint et `practice_attempts` existent.
- Baseline (2026-10-23T20:31Z, avant modification) : `npx tsc --noEmit` exit 0 ; `npx eslint` sur les 4 fichiers existants exit 0 ; `npm run build` exit 0 ; les 4 `grep -c` du DoD valent 0 (`PracticePanel.tsx` n'existe pas encore).
