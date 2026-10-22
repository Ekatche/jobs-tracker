---
task: Réécriture IA ciblée d'un passage sélectionné de la lettre de motivation
description: cover letter partial rewrite of a selected passage — POST /applications/{id}/cover-letter/rewrite (passage + instruction + full letter), cover_letter_crew.py rewrite_letter_passage_async with reviser LLM and prompt 05_rewrite_passage.md, errors raised not swallowed (RewriteFailedError → 502), outer whitespace of the selection preserved, wrapping quotes stripped only if passage unquoted, anti-hallucination detect_new_numbers warning with normalized numbers (1 000 / 30 % / 2,5), ApiUsageAction.LETTER_REWRITE quota in models.py / usage_tracker.py / admin.py ACTION_LABELS, lib/api.ts rewritePassage, CoverLetterPanel.tsx textarea selection toolbar quick instructions before/after preview accept/reject with stale-selection guard and readOnly while pending
status: done
created: 2026-10-22
---

# Réécriture ciblée d'un passage de lettre

## Context
- Existing code checked: `cover_letter_crew.py` (`_acompletion_retry`, `load_prompt` via `format_map`, `get_letter_llm("reviser")`, `build_completion_kwargs`, `ROLE_TEMPERATURES`, `_track_usage`) ; `_call_reviser` avale toute exception et rend le texte d'entrée (`except Exception` L504) : pattern à **ne pas** reprendre, la réécriture doit remonter l'erreur. `routers/cover_letters.py::get_cover_letter_pdf` (validation `ObjectId.is_valid` → 400, appartenance via `applications`) ; pattern quota `require_user_quota` + `record_api_usage` ; import paresseux du crew via `sys.path` comme dans `applications.py::_generate_cover_letter_bg` ; `llm/provider_errors.py::llm_http_exception` ; `usage_tracker.py::TIER_MONTHLY_LIMITS` ; `routers/admin.py::ACTION_LABELS` (libellé par action, repli sur la clé brute) ; `CoverLetterPanel.tsx` (`textarea` contrôlé `textBody`/`setTextBody`, `isDirty`, `isPending`, `handleSaveEdit` → PATCH = nouvelle version « edited »).
- Choix validés : sélection libre + consigne (rapide ou libre) → aperçu avant/après → Accepter/Rejeter ; l'acceptation remplace le passage dans l'éditeur, l'utilisateur enregistre via le flux existant ; quota dédié `LETTER_REWRITE`.
- Style : pas de `voice_style` ni de `writing_samples`. La lettre complète, envoyée en contexte, porte déjà le style du candidat ; on évite une lecture du profil et jusqu'à 6000 caractères d'exemples par appel.
- Fresh info looked up: n/a (litellm `acompletion` déjà utilisé à l'identique).
- Git status checked: `cover_letters.py`, `api.ts` et `CoverLetterPanel.tsx` portent les modifications non commitées du plan `20261022-letter-pdf-export` (done, archivé). **Pré-requis : commiter le travail PDF avant l'étape 1**, pour garder deux diffs séparés.

## Simpler Alternative Considered
Régénération complète avec consigne : coûteuse, réécrit tout le texte et perd les retouches manuelles. Rejetée par l'utilisateur.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py` (enum `ApiUsageAction`)
  - `backend/app/services/usage_tracker.py` (`TIER_MONTHLY_LIMITS`)
  - `backend/app/routers/admin.py` (`ACTION_LABELS`, une ligne)
  - `backend/app/llm/prompts/cover_letter/05_rewrite_passage.md` (nouveau)
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/app/routers/cover_letters.py`
  - `backend/tests/test_letter_rewrite.py` (nouveau)
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/applications/CoverLetterPanel.tsx`
- **Files NOT touched**: tous les autres, notamment le pipeline de génération complète, `letter_guards.py`, `frontend/src/app/settings/usage/page.tsx`, `frontend/src/types/usage.ts` (voir Notes)
- **Symbols replaced**: none
- **Symbols extended**: `ApiUsageAction`, `TIER_MONTHLY_LIMITS`, `ACTION_LABELS`, `coverLetterApi`, `CoverLetterPanel`
- **Symbols created**: `rewrite_letter_passage_async`, `detect_new_numbers`, `_preserve_outer_whitespace`, `RewriteFailedError`, `RewritePassageRequest`, endpoint `rewrite_cover_letter_passage`, `coverLetterApi.rewritePassage`

## Definition of Done
- [x] Build passes: `cd frontend && npm run build` (Next.js 15.2.4 exit 0)
- [x] Tests pass: `cd backend && uv run pytest tests/test_letter_rewrite.py tests/test_usage_tracker.py tests/test_cover_letters_api.py tests/test_cover_letter_crew.py -v` (67 passed, exit 0)
- [x] No dead code: n/a — none replaced
- [x] Type check: `cd frontend && npx tsc --noEmit` (0 errors, exit 0)
- [x] Quota dédié présent dans les 3 tiers : `grep -c 'LETTER_REWRITE' backend/app/services/usage_tracker.py` → 3
- [x] Libellé admin : `grep -c '"letter_rewrite"' backend/app/routers/admin.py` → 1
- [x] 400 identifiant invalide, 403 autre utilisateur, 422 passage absent de la lettre, 422 passage vide / blanc seul / > 2000 car. : `test_rewrite_invalid_id`, `test_rewrite_forbidden`, `test_rewrite_passage_not_in_letter`, `test_rewrite_validation`
- [x] Usage enregistré avec `ApiUsageAction.LETTER_REWRITE` après succès : `test_rewrite_records_usage` (LLM patché)
- [x] Erreur remontée, jamais avalée : sortie vide ou `finish_reason == "length"` → 502, aucun usage enregistré : `test_rewrite_empty_output_returns_502`
- [x] Blancs extérieurs du passage conservés (passage `"Phrase.\n\n"` → texte réécrit terminé par `"\n\n"`) : `test_rewrite_preserves_outer_whitespace`
- [x] Guillemets englobants retirés seulement si le passage d'origine n'en avait pas : `test_rewrite_strips_wrapping_quotes_only_if_passage_unquoted`
- [x] Garde anti-hallucination : « 40 % » absent de la lettre → avertissement ; « 1 000 »/« 1000 », « 30 % »/« 30% », « 2,5 »/« 2.5 » → aucun avertissement : `test_detect_new_numbers`
- [x] Prompt rendu sans accolade résiduelle et avec les 3 entrées : `test_rewrite_prompt_renders_inputs`
- [x] Le prompt interdit l'ajout de faits et impose de ne renvoyer que le passage : `grep -ci "n'ajoute aucun" backend/app/llm/prompts/cover_letter/05_rewrite_passage.md` ≥ 1
- [x] Aperçu avant/après + Accepter/Rejeter dans l'UI : `grep -cE 'Accepter|Rejeter' frontend/src/components/applications/CoverLetterPanel.tsx` ≥ 2
- [x] Éditeur verrouillé pendant une proposition : `grep -c 'readOnly' frontend/src/components/applications/CoverLetterPanel.tsx` ≥ 1
- [x] Garde de sélection périmée : `grep -c 'Le texte a changé' frontend/src/components/applications/CoverLetterPanel.tsx` ≥ 1
- [x] Manual check: en mode Éditer, sélectionner un paragraphe entier **avec** son saut de ligne final → « Plus concis » → l'aperçu s'affiche → Accepter remplace uniquement ce paragraphe et la séparation avec le paragraphe suivant reste intacte → Enregistrer crée v(n+1) « éditée » (observateur : utilisateur)

## Steps
- [x] Step 1: Ajouter `LETTER_REWRITE = "letter_rewrite"` à `ApiUsageAction`, les limites (FREE 20, ADVANCED 100, PRO None) dans `TIER_MONTHLY_LIMITS`, et `"letter_rewrite": "Réécritures de passage (lettres)"` dans `ACTION_LABELS` ; lancer `cd backend && uv run pytest tests/test_usage_tracker.py -v`.
- [x] Step 2: Créer `05_rewrite_passage.md`. Placeholders `{letter_text}`, `{passage}`, `{instruction}` uniquement : `load_prompt` passe par `format_map`, toute autre accolade doit être doublée (`{{ }}`). Règles : même langue que la lettre ; réécrire uniquement le passage, la lettre ne sert que de contexte ; n'ajoute aucun fait, chiffre, nom, outil ni entreprise absent de la lettre ; garder le ton et le registre du reste de la lettre ; longueur comparable sauf consigne contraire ; sortie = texte brut du passage seul, sans guillemets, balises ni commentaire. Consigne vide → « améliore la clarté sans changer le sens ».
- [x] Step 3: Dans `cover_letter_crew.py` :
  - `class RewriteFailedError(RuntimeError)`.
  - `rewrite_letter_passage_async(letter: str, passage: str, instruction: str) -> dict` : `get_letter_llm("reviser")`, `_acompletion_retry(model=..., api_key=..., messages=[...], max_completion_tokens=4000, drop_params=True, **build_completion_kwargs(llm.model, ROLE_TEMPERATURES["reviser"]))`. **Aucun `try/except` large** : les erreurs fournisseur remontent telles quelles. Sortie vide ou `finish_reason == "length"` → `RewriteFailedError`. Nettoyage dans cet ordre : clôtures ```, puis guillemets englobants (`« »`, `" "`, `“ ”`) retirés seulement si le passage d'origine (sans ses blancs) ne commence et ne finit pas lui-même par des guillemets, puis `_preserve_outer_whitespace(passage, text)` remet les blancs de début et de fin du passage autour du texte nettoyé. Retour `{"text", "warnings", "model", "input_tokens", "output_tokens"}`, où `warnings` est une liste de messages lisibles (ex. « Chiffre absent de la lettre d'origine : 40 % »).
  - `detect_new_numbers(original: str, rewritten: str) -> list[str]` : extraction des nombres par regex, normalisés avant comparaison (suppression des espaces, U+00A0 et U+202F entre chiffres ; virgule décimale → point ; `%` rattaché au nombre) ; renvoie les nombres de `rewritten` absents de `original`, où `original` est la **lettre complète**.
- [x] Step 4: Endpoint `POST /applications/{application_id}/cover-letter/rewrite`, modèle Pydantic `RewritePassageRequest` (`letter` 1–8000, `passage` 1–2000, `instruction` 0–500). Ordre : `ObjectId.is_valid` → 400 ; candidature introuvable → 404 ; appartenance → 403 ; `passage.strip()` vide ou `passage not in letter` → 422 ; `require_user_quota(..., ApiUsageAction.LETTER_REWRITE)` ; import paresseux du crew (même bloc `sys.path` que `_generate_cover_letter_bg`) ; `RewriteFailedError` → 502 « La réécriture n'a pas abouti, réessayez. » ; autre exception → `llm_http_exception(e) or HTTPException(502)` ; succès → `record_api_usage(action=LETTER_REWRITE, model=..., input_tokens=..., output_tokens=..., metadata={"application_id": ...})`. Retour `{"rewritten", "warnings"}`.
- [x] Step 5: Écrire `tests/test_letter_rewrite.py` (LLM patché sur `_acompletion_retry`, aucun appel réseau) avec les tests nommés dans le DoD ; lancer la suite du DoD.
- [x] Step 6: Front. `coverLetterApi.rewritePassage(applicationId, { letter, passage, instruction })` → `{ rewritten: string; warnings: string[] }`. Dans `CoverLetterPanel.tsx` :
  - `ref` + `onSelect` sur le textarea, qui mémorise `{ start, end }` quand la sélection n'est pas vide ;
  - barre d'action sous l'éditeur : chips Plus percutant / Plus concis / Corriger / Plus naturel + champ libre + Proposer, désactivée si `isPending` ou si une requête est en cours ;
  - le passage envoyé est exactement `textBody.slice(start, end)`, blancs compris (le backend les conserve) ;
  - pendant qu'une proposition est affichée, textarea en `readOnly` ;
  - panneau avant/après avec les avertissements ;
  - **Accepter** : si `textBody.slice(start, end) !== passage`, afficher « Le texte a changé depuis la proposition, relancez-la » et abandonner ; sinon remplacer par indices ;
  - **Rejeter** : abandonner la proposition.
  Puis `npm run build` et `npx tsc --noEmit`.
- [x] Step 7 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the new symbols (`rewrite_letter_passage_async`, `detect_new_numbers`, `_preserve_outer_whitespace`, `RewriteFailedError`, `RewritePassageRequest`, `rewritePassage`). Confirm 0 orphans.

## Code Review
- Dead code removed: None (purely additive scope)
- Build status: Clean (frontend npm run build exit 0, npx tsc --noEmit exit 0)
- Type errors: 0
- Unintended side effects: None observed
- Security surface touched: yes — validation d'entrée utilisateur envoyée à un LLM (bornes de taille 8000/2000/500, ObjectId validation, contrôle d'appartenance utilisateur, présence obligatoire du passage dans la lettre) ; semgrep run: 290 rules on 2 files, 0 findings
- Verdict: Approved

## Execution Log
- 2026-10-22T16:13Z | antigravity | step 1 | started
- 2026-10-22T16:15Z | antigravity | step 1 | done | LETTER_REWRITE in models, usage_tracker (3 tiers), admin ACTION_LABELS; pytest test_usage_tracker 12 passed exit 0
- 2026-10-22T16:15Z | antigravity | step 2 | started
- 2026-10-22T16:16Z | antigravity | step 2 | done | 05_rewrite_passage.md created, renders without orphan braces, rule count grep exit 0
- 2026-10-22T16:16Z | antigravity | step 3 | started
- 2026-10-22T16:20Z | antigravity | step 3 | done | cover_letter_crew.py updated with RewriteFailedError, _preserve_outer_whitespace, detect_new_numbers, rewrite_letter_passage_async; pytest test_cover_letter_crew 37 passed exit 0
- 2026-10-22T16:21Z | antigravity | step 4 | started
- 2026-10-22T16:22Z | antigravity | step 4 | done | RewritePassageRequest model & POST /applications/{id}/cover-letter/rewrite endpoint implemented in cover_letters.py
- 2026-10-22T16:23Z | antigravity | step 5 | started
- 2026-10-22T16:24Z | antigravity | step 5 | done | test_letter_rewrite.py created with 10 unit & API tests; full DoD suite 67 passed exit 0
- 2026-10-22T16:24Z | antigravity | step 6 | started
- 2026-10-22T16:29Z | antigravity | step 6 | done | lib/api.ts rewritePassage added; CoverLetterPanel.tsx selection tracking, chips, custom prompt, before/after preview, accept/reject and readOnly while pending implemented; npx tsc and npm run build passed exit 0
- 2026-10-22T16:30Z | antigravity | step 7 | started
- 2026-10-22T16:30Z | antigravity | step 7 | done | orphan scan on 6 new symbols completed with 0 orphans; semgrep 290 rules on 2 files 0 findings; DoD verified 100%

## Notes
- Preflight baseline (2026-10-22T16:13Z): pytest tests/test_usage_tracker.py tests/test_cover_letters_api.py exit 0 (20 passed), frontend tsc --noEmit exit 0. Convention files: AGENTS.md, GEMINI.md.
- 9 fichiers : au-dessus de la cible micro (1-5), mais périmètre bien délimité ; dépend du plan PDF pour les fichiers partagés (commit préalable).
- Revue du 2026-10-22 intégrée : blancs autour du passage, indices périmés, paramètres de voix retirés, erreurs remontées au lieu d'être avalées, `max_completion_tokens` fixé, guillemets, normalisation des nombres, libellé admin, `uv run pytest`.
- Hors périmètre : `settings/usage/page.tsx` et `types/usage.ts` ne listent ni `letter_rewrite` ni `role_suggestion` → pas de carte de quota sur la page Usage, l'historique affiche la clé brute (repli existant). À traiter dans un plan séparé si voulu.
- `DISABLE_QUOTA_BLOCKING` vaut `true` par défaut : le quota est compté mais ne bloque pas, comme pour les autres actions.
- Coût estimé, non mesuré, avec le réviseur GPT-6.1 Sol (2 $ / 10 $ par M tokens) : ~2 500 tokens d'entrée + ~1 500 de sortie et réflexion ≈ 0,02 $ par réécriture.
