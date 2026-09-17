---
task: Corriger le prompt réviseur qui ne reçoit aucune donnée, et ajouter un champ UI pour le voice DNA (writing_style)
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Contexte manquant dans le prompt réviseur + champ UI voice DNA

## Context

- Existing code checked :
  - `backend/app/llm/prompts/cover_letter/04_revision.md` (123 lignes, lu intégralement) — décrit dans son intro que le modèle "dispose de" la lettre originale, du JSON d'analyse, des défauts du critique et des violations de garde-fous, mais ne contient **aucun placeholder** `{letter_text}` / `{analyst_json}` / `{critic_flaws}` / `{violations}` nulle part dans le fichier. Seuls `{min_words}`/`{max_words}` sont interpolés.
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py:301-320` (`_call_reviser`, déjà `async def` suite au commit `2083b38`) — appelle `load_prompt("04_revision", min_words=..., max_words=..., letter_text=letter_text, violations=violations, critic_flaws=critic_flaws)`. Comme le template ne référence pas ces clés, `str.format(**context)` les ignore silencieusement (un kwarg en trop ne lève pas d'erreur) : le prompt envoyé au LLM ne contient que des instructions, zéro donnée. Constaté en prod : le modèle répond en demandant qu'on lui fournisse "la lettre originale, le JSON d'analyse factuelle, les défauts relevés par le critique et les violations des garde-fous déterministes" — soit une paraphrase quasi littérale de l'intro du prompt qu'il n'a reçu que comme texte, jamais rempli. Le paramètre `analyst_json` de la fonction n'est en plus jamais transmis à `load_prompt` : mort, jamais câblé, alors que la section "## Faits" du prompt affirme que ce JSON est "la seule source de vérité factuelle" pour la révision.
  - `backend/tests/test_cover_letter_crew.py` — aucun test n'inspecte le contenu du prompt envoyé par `_call_reviser` (les tests existants vérifient seulement `max_completion_tokens`, températures, et le comportement de haut niveau du pipeline). Rien ne couvre la régression trouvée.
  - `frontend/src/types/coverLetter.ts:45-63` (`CandidateProfile`) — pas de champ `writing_style`. Le backend (`backend/app/models.py`, `backend/app/services/profile/merge.py`) l'a déjà, ajouté et mergé par un plan précédent (`docs/micro/20260916-letter-company-research-voice-dna/PLAN.md`, commit `95f4743`), volontairement laissé backend-only à l'époque (pas de champ UI dans le scope de ce plan-là).
  - `frontend/src/components/profile/CandidateProfileSection.tsx` (1126 lignes) — pattern de champ texte simple déjà établi avec `summary` : `useState` (ligne 62) → rempli dans `populateForm` (ligne 92) → inclus dans `updatedProfile` avant `coverLetterApi.updateCandidateProfile` (ligne 267) → `<textarea>` contrôlé (lignes 784-796, juste après le bouton d'import GitHub). `PUT /profile/candidate` (backend, déjà vérifié dans le plan précédent) accepte déjà n'importe quel champ du dict envoyé — aucun changement d'endpoint nécessaire.
  - Git status checked : arbre propre au moment d'écrire ce plan (un rewrite async concurrent non lié a été trouvé, committé séparément en `2083b38` avec l'accord de l'utilisateur avant de démarrer ce plan).

- Fresh info looked up : n/a — pas de nouvelle librairie, `str.format` et React `useState` sont déjà utilisés partout dans ces fichiers.

## Simpler Alternative Considered

Pour le bug réviseur : aucune — c'est un oubli direct (placeholders manquants), la seule réparation sensée est de les ajouter au prompt et de les câbler dans l'appel. Pas de réécriture plus large du prompt : le style/les règles de révision restent celles que l'utilisateur a écrites, seul le bloc de données manque.

Pour le champ voice DNA : suivre exactement le pattern `summary` existant plutôt qu'introduire un nouveau pattern de champ (ex. modal séparée, composant dédié) — c'est la version minimale cohérente avec le reste du composant.

## Surgical Scope

- **Files touched** :
  - `backend/app/llm/prompts/cover_letter/04_revision.md`
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/tests/test_cover_letter_crew.py`
  - `frontend/src/types/coverLetter.ts`
  - `frontend/src/components/profile/CandidateProfileSection.tsx`
- **Files NOT touched** : tout le reste, notamment `backend/app/routers/cover_letters.py` (endpoint déjà générique), `backend/app/services/profile/merge.py` et `backend/app/models.py` (déjà faits dans le plan précédent), `backend/job_trackers/src/job_trackers/letter_llm.py`.
- **Symbols replaced** (→ à supprimer avant la fin) : aucun.
- **Symbols extended** (→ à garder) :
  - `04_revision.md` — nouvelle section `## Contexte` avec les placeholders manquants.
  - `_call_reviser` — même signature, corrige uniquement les kwargs passés à `load_prompt`.
  - `CandidateProfile` (frontend) — un champ optionnel de plus.
  - `CandidateProfileSection` — un `useState` de plus, `populateForm`/payload/JSX étendus.

## Definition of Done

- [x] Build passes : `cd frontend && npm run build` (Next.js 15.2.4 build réussi sans erreur)
- [x] Tests pass : `cd backend && uv run --no-sync pytest tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py -v` (17/17 passés dans jobtracker-backend)
- [x] No dead code : aucun symbole remplacé ni orphelin détecté
- [x] Type check : couvert par `npm run build` (TypeScript validé sans erreur)
- [x] Manual check : `cd backend && python3 -c "from pathlib import Path; t = Path('app/llm/prompts/cover_letter/04_revision.md').read_text(encoding='utf-8'); print(t.format(min_words=270, max_words=330, letter_text='Lettre test', analyst_json='{}', critic_flaws='[]', violations='[]'))"` — validé sans KeyError

## Steps

- [x] Step 1 : `04_revision.md` — ajouter une section `## Contexte` (après `## Longueur`, avant `## Contrôle final`) avec quatre placeholders : lettre originale (`{letter_text}`), JSON d'analyse factuelle (`{analyst_json}`), défauts identifiés par le critique (`{critic_flaws}`), violations des garde-fous déterministes (`{violations}`).
- [x] Step 2 : `cover_letter_crew.py::_call_reviser` — passer `analyst_json=json.dumps(analyst_json, ensure_ascii=False)`, `critic_flaws=json.dumps(critic_flaws, ensure_ascii=False)`, `violations=json.dumps(violations, ensure_ascii=False)` à `load_prompt` (au lieu des listes/dict Python bruts, pour cohérence avec le reste du fichier qui `json.dumps` déjà `missions`/`selected_experiences` ailleurs). `letter_text` reste une chaîne brute.
- [x] Step 3 : `test_cover_letter_crew.py` — ajouter `test_reviser_prompt_includes_letter_and_analysis_data` : mock `acompletion`, appeler `_call_reviser` avec un `letter_text`, un `analyst_json` contenant une mission identifiable, une liste `critic_flaws` non vide, un `guard_report` avec une violation ; asserter que le prompt envoyé (`mock_comp.call_args`) contient la lettre, la mission du JSON d'analyse, le défaut du critique et la violation.
- [x] Step 4 : `frontend/src/types/coverLetter.ts` — ajouter `writing_style?: string;` à `CandidateProfile` (juste après `summary?: string;`).
- [x] Step 5 : `CandidateProfileSection.tsx` — ajouter `const [writingStyle, setWritingStyle] = useState("");` (près de `summary`), le remplir dans `populateForm` (`setWritingStyle(data.writing_style || "")`), l'inclure dans `updatedProfile` (`writing_style: writingStyle`), et ajouter un `<textarea>` contrôlé juste après celui de `summary` (lignes ~784-796), avec un label du type "Style d'écriture personnel (voice DNA)" et un placeholder expliquant que ce texte guide le ton des lettres générées. Affichage également inclus en mode lecture.
- [x] Step 6 (teardown) : relancer la suite de tests Python du Definition of Done + `npm run build`. Scanner les imports/variables devenus orphelins dans les fichiers touchés (aucun symbole supprimé, scan de confirmation seulement). Confirmer 0 orphelin.

## Code Review
- Dead code removed: aucun symbole orphelin ou mort.
- Build status: 17/17 tests pytest passés (`test_cover_letter_crew.py` et `test_cover_letter_prompts.py`), `npm run build` réussi sans erreur.
- Type errors: 0 erreur TypeScript.
- Unintended side effects: aucun, diff chirurgical sur 5 fichiers.
- Security surface touched: aucun secret exposé, validation stricte conservée.
- Verdict: ✅ DONE

## Execution Log
- 2026-09-16 21:07 Step 1 complete. Added `## Contexte` section to `04_revision.md` with `{letter_text}`, `{analyst_json}`, `{critic_flaws}`, and `{violations}` placeholders. Verified via `python3` format assertion without KeyError.
- 2026-09-16 21:10 Step 2 complete. Passed `json.dumps(analyst_json)`, `json.dumps(critic_flaws)`, and `json.dumps(violations)` to `load_prompt` in `_call_reviser` (`cover_letter_crew.py`). Existing test suite passed (11/11).
- 2026-09-16 21:12 Step 3 complete. Added `test_reviser_prompt_includes_letter_and_analysis_data` asserting reviser prompt includes original letter, factual analysis mission, critic flaws, and guard violations. Verified via `pytest tests/test_cover_letter_crew.py -v` (12/12 passed).
- 2026-09-16 21:13 Step 4 complete. Added `writing_style?: string;` to `CandidateProfile` in `frontend/src/types/coverLetter.ts`.
- 2026-09-16 21:22 Step 5 complete. Added `writing_style` state, `populateForm` mapping, payload in `handleSave`, `<textarea>` in edit mode and styled display in view mode in `CandidateProfileSection.tsx`.
- 2026-09-16 21:24 Step 6 complete. Ran full test suite in docker (17/17 passed) and `npm run build` (success). 0 dead code.

## Notes
(deviations from plan, errors hit, corrections made)
