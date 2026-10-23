---
task: Corriger la sélection périmée du passage à réécrire dans l'éditeur de lettre
description: fix stale passage selection in cover letter partial rewrite — CoverLetterPanel.tsx handleTextareaSelect ignores collapsed selection (click elsewhere keeps old "X car. sélectionnés"), selection offsets reused after textBody changes (typing, polling, accept) so rewritePassage slices wrong passage; selection now stores letter snapshot, selectedPassage derived only when selection.letter === textBody, cleared on preview toggle and handleSaveEdit; React onSelect textarea Next.js frontend
status: done
created: 2026-10-22
---

# Corriger la sélection périmée du passage à réécrire

## Context
- Existing code checked: `frontend/src/components/applications/CoverLetterPanel.tsx`
  - L55 : état `selection: { start, end } | null`.
  - L170-175 `handleTextareaSelect` : ne met à jour la sélection que si elle est non vide. Un clic ailleurs dans la zone de texte (curseur sans sélection) laisse l'ancienne en place : la barre affiche encore « X car. sélectionnés » et les boutons restent actifs.
  - L177-180 `handleRewrite` : découpe `textBody` avec les anciennes positions. Si le texte a changé depuis la sélection (frappe, fin de génération par polling L100, acceptation d'une proposition), le passage envoyé à `coverLetterApi.rewritePassage` n'est plus celui qui avait été sélectionné.
  - L235-238 `selectedPassage` : dérivé de `selection` et `textBody` sans vérifier que le texte est resté le même.
  - L381-385 (bouton Aperçu) et L139-150 `handleSaveEdit` : passent en aperçu sans effacer la sélection. La zone de texte est démontée, mais au retour en édition la barre annonce une sélection qui n'est plus visible.
  - Plan d'origine : `docs/micro/archive/2026-10/20261022-letter-partial-rewrite/PLAN.md`. Il ne comportait pas de test frontend (aucun lanceur de tests dans `frontend/package.json`).
- Fresh info looked up: le plugin `SelectEventPlugin` de React ne déclenche pas `onSelect` quand le focus quitte la zone de texte (`focusout` remet `activeElement` à null). Cliquer sur un bouton « Plus concis » ou dans le champ de consigne ne vide donc pas la sélection. Le scénario D de l'étape 4 le vérifie en vrai.
- Git status checked: arbre propre sur `27de801`. Seul changement : le plan `20261022-cv-page-budget-by-relevance` a été archivé (`git mv`) et son lien dans INDEX.md réécrit.

## Simpler Alternative Considered
Effacer la sélection dans `onChange` de la zone de texte. Ça ne couvre pas les autres changements du texte : la fin du polling (`fetchLetter` → `setTextBody`) et l'acceptation d'une proposition. Une sélection qui garde le texte sur lequel elle a été faite couvre tous les cas, en une seule comparaison.

## Surgical Scope
- **Files touched**: `frontend/src/components/applications/CoverLetterPanel.tsx`
- **Files NOT touched**: tous les autres. Backend, `lib/api.ts` et prompts sont inchangés.
- **Symbols replaced** (→ to delete before done): aucun. Le découpage propre à `handleRewrite` (`textBody.slice(selection.start, selection.end)` et `if (!selection || selection.start >= selection.end)`) disparaît au profit de `selectedPassage`.
- **Symbols extended** (→ keep): l'état `selection` (champ `letter` ajouté), `handleTextareaSelect`, `handleRewrite`, `selectedPassage` (déplacé au-dessus des gestionnaires), `handleSaveEdit`, le bouton Aperçu.

## Definition of Done
- [x] Build passes: `cd frontend && npm run build` exit 0
- [x] Tests pass: n/a. Le frontend n'a aucun lanceur de tests (ni jest, ni vitest, ni testing-library dans `frontend/package.json`). La vérification du comportement passe par le contrôle manuel de l'étape 4.
- [x] No dead code: `grep -c 'textBody.slice(selection.start, selection.end)' frontend/src/components/applications/CoverLetterPanel.tsx` vaut 1 (seulement dans `selectedPassage`).
- [x] Type check: `cd frontend && npx tsc --noEmit` exit 0
- [x] Lint: `cd frontend && npm run lint` ne montre aucun nouvel avertissement sur `CoverLetterPanel.tsx` par rapport à la référence de départ.
- [x] Bug texte modifié (L496) : `grep -c 'selection.letter === textBody' frontend/src/components/applications/CoverLetterPanel.tsx` vaut 1.
- [x] Bug clic ailleurs (L170) : `grep -c 'setSelection(null)' frontend/src/components/applications/CoverLetterPanel.tsx` vaut 4 (régénération, acceptation, bouton Aperçu, enregistrement). La sélection vide passe par le `: null` de `handleTextareaSelect`.
- [x] Manual check: scénarios A à D de l'étape 4, tous conformes, sur http://localhost:3875 (Docker local en mode dev, rechargement à chaud).

## Steps
- [x] Step 1: Faire porter à `selection` le texte de la lettre au moment de la sélection : type `{ start: number; end: number; letter: string } | null`. Réécrire `handleTextareaSelect` pour qu'une sélection vide la remette à `null` et qu'une sélection non vide enregistre `{ start, end, letter: e.currentTarget.value }`. Vérif : `cd frontend && npx tsc --noEmit`. Une erreur de type est attendue tant que l'étape 2 n'est pas faite ; si c'est le cas, l'étape 1 se valide avec la commande de l'étape 2.
- [x] Step 2: Déplacer `selectedPassage` au-dessus de `handleTextareaSelect`. Ne le dériver que si `selection.letter === textBody`, sinon chaîne vide. Dans `handleRewrite`, remplacer la garde et le découpage par `if (!selection || !selectedPassage.trim()) return;` et `const passage = selectedPassage;`. Vérif : `cd frontend && npx tsc --noEmit` exit 0, et les deux `grep -c` de la DoD (letter, slice) valent 1.
- [x] Step 3: Ajouter `setSelection(null)` dans `onClick` du bouton Aperçu et dans `handleSaveEdit`. Vérif : `grep -c 'setSelection(null)'` vaut 4, et `cd frontend && npx tsc --noEmit` exit 0.
- [x] Step 4: Contrôle manuel sur http://localhost:3875, sur une candidature qui a une lettre prête, en mode Édition. Observateur : Claude via chrome-devtools si une session connectée est disponible, sinon l'utilisateur.
  - (A) Sélectionner un passage puis cliquer ailleurs dans la zone de texte : la barre affiche « (sélectionnez d'abord du texte dans l'éditeur) » et les boutons rapides sont désactivés.
  - (B) Sélectionner un passage puis taper un mot avant lui : même résultat qu'en A.
  - (C) Sélectionner un passage, passer en Aperçu puis revenir en Édition : même résultat qu'en A.
  - (D) Non-régression : sélectionner un passage et cliquer « Plus concis ». La proposition s'affiche et son « Passage original » est exactement le texte sélectionné. Ce scénario fait un appel LLM, environ 0,02 $.
- [x] Step 5 (teardown): Pas de symbole remplacé. Confirmer qu'il ne reste aucun reliquat du découpage de `handleRewrite` (`grep -c 'selection.start >= selection.end'` vaut 0), puis lancer `npm run lint` et `npm run build`.

## Code Review
- Dead code removed: yes. L'ancien `selectedPassage` (garde `selection.start < selection.end`) et le découpage propre à `handleRewrite` ont disparu : slice=1, oldguard=0.
- Build status: pass (`npm run build` exit 0)
- Type errors: none (`npx tsc --noEmit` exit 0)
- Unintended side effects: none. Diff relu en entier (+22 −13, un seul fichier) : chaque ligne relève des étapes 1 à 3. Changement de comportement voulu : passer en Aperçu ou enregistrer efface désormais la sélection.
- Security surface touched: no (état React local, aucun appel réseau ni validation modifiés)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-22T19:56Z | claude-code | preflight | baseline | tsc exit 0, lint exit 0 (0 warning CoverLetterPanel), build exit 0, greps slice=2 letter=0 null=2 oldguard=1
- 2026-10-22T19:56Z | claude-code | step 1 | started
- 2026-10-22T19:56Z | claude-code | step 1 | done | `npx tsc --noEmit` exit 0
- 2026-10-22T19:56Z | claude-code | step 2 | started
- 2026-10-22T19:57Z | claude-code | step 2 | done | `npx tsc --noEmit` exit 0, grep letter=1 slice=1
- 2026-10-22T19:57Z | claude-code | step 3 | started
- 2026-10-22T19:57Z | claude-code | step 3 | done | `npx tsc --noEmit` exit 0, grep setSelection(null)=4
- 2026-10-22T19:57Z | claude-code | step 4 | started
- 2026-10-22T20:21Z | claude-code | step 4 | done | banc isolé A-D + polling OK (voir Notes) ; utilisateur a testé sur localhost:3875 et répondu « ok »
- 2026-10-22T20:21Z | claude-code | step 5 | started
- 2026-10-22T20:21Z | claude-code | step 5 | done | oldguard=0, `npm run lint` exit 0 (0 warning CoverLetterPanel), `npm run build` exit 0
- 2026-10-22T20:21Z | claude-code | close out | done | DoD complète relancée : tsc 0, lint 0, build 0, slice=1 letter=1 null=4 oldguard=0 ; diff relu

## Notes
- 2026-10-22T19:52Z : plan écrit après le déploiement de `27de801`. Les deux bugs sont en prod sur le VPS depuis `cc18bbe`.
- Plan validé par l'utilisateur (« ok c'est bon ça fonctionne, déploie-le »). Le déploiement sur le VPS (commit, push, rebuild du frontend) est demandé explicitement après la clôture.
- Fichiers de convention lus : `CLAUDE.md`, `AGENTS.md` (identique à `GEMINI.md`), `.cursorrules`. Aucune règle propre au frontend : ils portent sur l'usage du graphe de code et la gestion des tests backend.
- Référence de départ (2026-10-22T19:56Z) :
  - `npx tsc --noEmit` exit 0 ;
  - `npm run lint` exit 0, aucun avertissement sur `CoverLetterPanel.tsx` (un avertissement préexistant `exhaustive-deps` `loadPdf` dans un autre fichier) ;
  - `npm run build` exit 0 ;
  - comptes `grep` : slice = 2, letter = 0, `setSelection(null)` = 2, ancienne garde = 1.
- Étape 4, 2026-10-22T20:00Z : le Chrome piloté par chrome-devtools n'a pas de session sur http://localhost:3875 (redirection vers `/auth/login`).
  - Banc isolé en attendant : `scratchpad/selection-bench/index.html`. Il reprend à l'identique la logique de sélection du composant corrigé, avec React 19.1.0 (même version que `frontend/node_modules`) et de vrais événements clavier et souris.
  - (D) Sélection par Shift+flèches, clic sur « Plus concis » : passage envoyé identique à la sélection (65 car.). Même résultat en passant par le champ de consigne libre puis « Proposer » : cliquer sur un bouton ou un champ ne vide pas la sélection.
  - (A) Clic ailleurs dans la zone de texte : la barre affiche « (sélectionnez d'abord… ) », bouton désactivé.
  - (B) Sélection puis frappe de « Hello » : même résultat.
  - Polling simulé (texte remplacé sans événement de sélection) : sélection invalidée.
  - (C) Aperçu puis Édition : sélection effacée.
  - Reste : le contrôle dans la vraie appli, avec la session de l'utilisateur.
- Avant l'étape 5, sans la cocher : `npm run lint` exit 0 sans avertissement sur `CoverLetterPanel.tsx`, `npm run build` exit 0.
- 2026-10-22T20:21Z : l'utilisateur a validé sur localhost (« ok »). Plan clos. Prochaine action : commit, push et déploiement du frontend sur le VPS.
