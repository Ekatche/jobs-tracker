---
task: Mode entraînement du kit d'entretien, partie backend — noter une réponse écrite à une question anticipée et garder l'historique
description: interview prep practice mode backend — POST /offers/{offer_id}/interview-prep/practice (FastAPI, interview_prep.py) scores a written answer to an AnticipatedQuestion via LiteLLM acompletion DEFAULT_INTERVIEW_MODEL, new prompt answer_feedback.md, evaluate_practice_answer in interview_prep_service.py (4 criteria structure STAR / quantified_result / offer_fit / coverage 1-5, overall_score average computed server-side, missing points, improved_answer), _mask_invented_numbers anti-hallucination guard replacing numbers absent from answer + linked STAR story with [à chiffrer], record_api_usage sub_action practice, require_user_quota, Pydantic PracticeCriterion PracticeAttempt, InterviewPrep.practice_attempts history pushed with MongoDB $push, attempts purged when their question disappears (generate questions / generate all reset, PUT update filter by question_id)
status: done
created: 2026-10-23
---

# Mode entraînement — backend : noter une réponse et garder l'historique

## Context
- Existing code checked :
  - `backend/app/models.py` l. 767-840 : `StarRStory`, `AnticipatedQuestion` (a un `id` uuid, `mapped_story_id`, `key_points_to_cover`), `InterviewPrep` (aucun champ d'entraînement).
  - `backend/app/services/interview_prep_service.py` : les 4 `generate_*` suivent le même schéma (prompt `.md` + `template.format`, `acompletion(model=DEFAULT_INTERVIEW_MODEL, drop_params=True, **build_completion_kwargs(...))`, `record_api_usage(..., metadata={"sub_action", "offer_id"})`, `_clean_json_output`). Helpers réutilisables : `format_evaluation_context` (l. 73), `_offer_role_and_company` (l. 129).
  - `backend/app/routers/interview_prep.py` : `_get_prep_or_empty`, `_get_profile_and_offer` (évaluation filtrée par utilisateur), `require_user_quota`. `generate_all` et `PUT` écrivent des champs précis par `$set`. `generate_stories_endpoint` (l. 128-134) remet à `None` les `mapped_story_id` d'histoires disparues : c'est le modèle suivi pour purger les essais dont la question a disparu. L'export fait `InterviewPrep(**prep_doc)`.
  - Convention de validation : `cover_letters.py` l. 196-198 (`Field(..., min_length=1, max_length=...)`).
  - Tests : `test_interview_prep_service.py` (LLM mocké via `patch("app.services.interview_prep_service.acompletion")`, test paramétré de `temperature` l. 316), `test_interview_prep_api.py` (Mongo de test, `require_user_quota` et générateurs patchés).
  - Modèle : `DEFAULT_INTERVIEW_MODEL` vaut Flash par défaut dans le code, mais `INTERVIEW_PREP_MODEL` le fixe à `openai/gpt-6.1-sol` en local (logs backend du 23/10). Banc du 30/09 : Flash invente des résultats chiffrés (ancrage 4,4/10).
  - Plans passés : `20261023-interview-prep-cancel-generation` et `20261023-interview-prep-edit-stories-confirm-regen` (même routeur, même fichier de tests).
- Fresh info looked up : n/a, aucune nouvelle librairie (LiteLLM, Pydantic et Motor sont déjà utilisés de la même façon).
- Git status checked : `interview_prep.py` et `test_interview_prep_api.py` portent les changements non commités des plans A et C de cette session (clos, connus). `models.py`, `interview_prep_service.py` et `test_interview_prep_service.py` sont propres. Les autres fichiers modifiés (`jobboards.py`, `pyproject.toml`, `uv.lock`, etc.) viennent d'autres sessions et sont hors périmètre.

## Simpler Alternative Considered
- Envoyer le texte de la question depuis le client au lieu de son `id` : moins de code, mais le serveur perdrait l'accès fiable aux points clés et à l'histoire liée, et accepterait n'importe quelle question. Écarté.
- Une collection séparée pour l'historique : inutile, le document `interview_preps` est déjà renvoyé par `GET` et filtré par utilisateur. L'historique y va par `$push`.
- Pas de garde déterministe sur les chiffres, seulement la consigne dans le prompt : plus simple, mais la « version retravaillée » est un texte que l'utilisateur répétera en entretien, et le modèle par défaut du code (Flash) invente des chiffres. La garde fait une dizaine de lignes et se teste sans LLM. Gardée.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/llm/prompts/interview/answer_feedback.md` (nouveau)
  - `backend/app/services/interview_prep_service.py`
  - `backend/app/routers/interview_prep.py`
  - `backend/tests/test_interview_prep_service.py`
  - `backend/tests/test_interview_prep_api.py`
- **Files NOT touched**: tout le reste, en particulier le frontend (plan séparé `20261023-interview-practice-panel-ui`), `export_interview_prep_markdown` (l'export n'inclut pas l'historique), les autres prompts, `usage_tracker.py`.
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `InterviewPrep` (+ `practice_attempts`)
  - `generate_questions_endpoint`, `generate_all_endpoint`, `update_interview_prep` (purge des essais dont la question a disparu)
  - `test_generators_omit_temperature_for_models_that_reject_it` (+ appel à `evaluate_practice_answer`)
  - Nouveaux : `PracticeCriterion`, `PracticeAttempt`, `evaluate_practice_answer`, `_mask_invented_numbers`, `PracticeAnswerRequest`, `practice_answer_endpoint`

## Definition of Done
- [x] Lint : `cd backend && uv run ruff check app/models.py app/services/interview_prep_service.py app/routers/interview_prep.py tests/test_interview_prep_service.py tests/test_interview_prep_api.py` (exit 0)
- [x] Tests : `cd backend && uv run pytest tests/test_interview_prep_api.py tests/test_interview_prep_service.py tests/test_interview_prep_models.py -v`. Tous verts. Exige le Mongo de test du `conftest.py` (port 27018), convention du dépôt.
- [x] Nouveaux tests présents : `cd backend && uv run pytest tests/test_interview_prep_api.py tests/test_interview_prep_service.py -k practice -v` → 8 passed.
- [x] Pas d'essai orphelin : `cd backend && uv run pytest tests/test_interview_prep_api.py -k "cleared_when_questions_regenerated or kept_for_remaining_questions" -v` → 2 passed.
- [x] Même modèle que le reste du kit, aucun nouveau modèle : `grep -c "model=DEFAULT_INTERVIEW_MODEL" backend/app/services/interview_prep_service.py` vaut 5 (4 aujourd'hui).
- [x] Coût suivi : `grep -c '"sub_action": "practice"' backend/app/services/interview_prep_service.py` vaut 1.
- [x] Quota vérifié : `grep -c "require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)" backend/app/routers/interview_prep.py` vaut 6 (5 aujourd'hui).
- [x] Consigne anti-invention dans le prompt : `grep -c "\[à chiffrer\]" backend/app/llm/prompts/interview/answer_feedback.md` ≥ 1.
- [x] Longueur de réponse plafonnée : `grep -c "max_length=6000" backend/app/routers/interview_prep.py` vaut 1.
- [x] No dead code : n/a, aucun symbole remplacé. ruff ne signale aucun import inutilisé.
- [x] Type check : n/a, aucun vérificateur de types configuré côté backend (ni mypy ni pyright dans `pyproject.toml`).
- [x] Manual check : `curl -s http://localhost:8000/openapi.json | grep -c 'interview-prep/practice'` ≥ 1 (backend local en `--reload`). Le scénario de bout en bout se fait dans le plan frontend.

## Steps
- [x] Step 1 : `models.py`.
  - `PracticeCriterion` : `key: str`, `score: int = Field(ge=1, le=5)`, `comment: str`.
  - `PracticeAttempt` : `id` (uuid), `question_id`, `question` (copie du texte, qui survit à une régénération des questions), `answer`, `criteria: List[PracticeCriterion]`, `overall_score: float`, `missing: List[str]`, `improved_answer: str`, `created_at` (`utcnow_with_timezone`).
  - `InterviewPrep.practice_attempts: List[PracticeAttempt] = Field(default_factory=list)`.
  - Vérif : `uv run pytest tests/test_interview_prep_models.py -v`.
- [x] Step 2 : prompt `answer_feedback.md`, même style que `anticipated_questions.md`.
  - Contexte : offre (entreprise, poste, description), évaluation (exigences Bloc B), question, catégorie, points clés, histoire STAR+R liée, réponse du candidat.
  - Les 4 critères notés de 1 à 5, avec un commentaire d'une phrase :
    - `structure` : STAR complet pour une question comportementale, raisonnement structuré pour une question technique ;
    - `quantified_result` : résultat chiffré ;
    - `offer_fit` : adéquation aux exigences de l'offre ;
    - `coverage` : points clés couverts et cohérence avec l'histoire liée.
  - `missing` : 2 à 5 manques concrets.
  - `improved_answer` : réponse orale à la première personne, 150 à 250 mots, qui reprend uniquement les faits de la réponse et de l'histoire liée. Aucun chiffre, outil, nom ou résultat absent de ces deux sources : écrire `[à chiffrer]` à la place.
  - Sortie : un objet JSON. Accolades doublées pour `template.format`.
  - Vérif : `grep -c "\[à chiffrer\]"` ≥ 1, et rendu `template.format(...)` sans `KeyError` (couvert par le test de l'étape 3).
- [x] Step 3 : service.
  - `evaluate_practice_answer(db, user_id, offer, evaluation, question, answer, story=None) -> PracticeAttempt` : même schéma que `generate_anticipated_questions`, avec `sub_action: "practice"` et une température de 0.2.
  - Critères construits dans l'ordre fixe `PRACTICE_CRITERIA`, scores ramenés dans 1..5, `ValueError` si un critère manque. `overall_score` est la moyenne calculée par le serveur, arrondie à 1 décimale.
  - `_mask_invented_numbers(text, sources)` : chaque nombre isolé (`\b\d+(?:[.,]\d+)?\b`) absent des sources (réponse et histoire liée) devient `[à chiffrer]`. Appliqué à `improved_answer`.
  - Tests dans `test_interview_prep_service.py` :
    - `test_practice_evaluate_scores_and_average` : ordre des critères, scores 0 et 7 ramenés à 1 et 5, moyenne, copie de la question, `sub_action`. Le prompt contient la réponse, la situation de l'histoire et un point clé.
    - `test_practice_evaluate_rejects_missing_criterion`.
    - `test_practice_mask_invented_numbers` : un nombre inventé est masqué, un nombre présent dans les sources est gardé, `K8s` et `S3` sont intacts.
    - Étendre le test de `temperature` à `evaluate_practice_answer` (5 appels).
  - Vérif : `uv run pytest tests/test_interview_prep_service.py -v`.
- [x] Step 4 : routeur.
  - `PracticeAnswerRequest` : `question_id: str = Field(..., min_length=1, max_length=64)`, `answer: str = Field(..., min_length=1, max_length=6000)`.
  - `POST /offers/{offer_id}/interview-prep/practice`, dans cet ordre :
    1. `require_user_quota` ;
    2. `_get_profile_and_offer` (offre et évaluation de l'utilisateur ; le profil n'entre pas dans le prompt) ;
    3. recherche de la question par `id` dans le kit de l'utilisateur, 404 « Question introuvable dans le kit. » sinon ;
    4. recherche de l'histoire liée ;
    5. appel au service ;
    6. `$push` de la tentative dans `practice_attempts` et `$set` de `updated_at`, sans upsert ;
    7. renvoi du kit sérialisé.
  - Pas de vérification d'annulation : appel court, et une tentative payée mérite d'être gardée.
  - Tests dans `test_interview_prep_api.py` :
    - `test_practice_appends_attempt_to_history` : 2 POST donnent 2 tentatives dans l'ordre ; le service reçoit l'histoire liée et la réponse ; l'export répond 200 avec des tentatives présentes.
    - `test_practice_unknown_question_returns_404` : le service n'est pas appelé.
    - `test_practice_ignores_other_users_prep` : la question existe seulement dans le kit d'un autre compte, d'où un 404, et le document de l'autre compte reste intact.
  - Vérif : `uv run pytest tests/test_interview_prep_api.py -v`.
- [x] Step 5 : pas d'essai sans sa question.
  - `generate_questions_endpoint` et `generate_all_endpoint` : `practice_attempts` remis à `[]` dans le `$set`. Les nouvelles questions ont toutes de nouveaux `id`, donc aucun essai ne leur correspond.
  - `update_interview_prep` : quand `anticipated_questions` est fourni, ne garder que les essais dont le `question_id` reste dans la liste.
  - Tests dans `test_interview_prep_api.py` :
    - `test_practice_attempts_cleared_when_questions_regenerated` ;
    - `test_practice_attempts_kept_for_remaining_questions_on_update` : un PUT qui retire une question supprime ses essais et garde ceux de l'autre.
  - Vérif : `uv run pytest tests/test_interview_prep_api.py -v`.
- [x] Step 6 (teardown) : aucun symbole remplacé, donc pas de scan d'orphelins. Relancer tout le DoD (ruff, pytest sur les 3 fichiers, les `grep -c`, `curl openapi.json`) et relire le diff ligne à ligne.

## Code Review
- Dead code removed: n/a, aucun symbole remplacé. ruff ne signale aucun import inutilisé.
- Build status: pass. ruff exit 0. pytest sur les 3 fichiers : 29 passed (`-k practice` 8 passed, orphelins 2 passed). Les tests du service n'utilisent que des mocks. Les tests d'API utilisent le Mongo de test du `conftest.py` (port 27018), convention du dépôt.
- Type errors: n/a, aucun vérificateur de types côté backend.
- Unintended side effects: aucun.
  - `update_interview_prep` construit maintenant son document de mise à jour avant les `if`, pour pouvoir y ajouter le `$pull`. Le comportement des autres champs ne change pas : `test_update_and_export_interview_prep` est vert.
  - Limite connue, non traitée : si les questions sont régénérées ou retirées pendant l'appel LLM d'un essai (quelques secondes), le `$push` qui suit peut laisser un essai orphelin. Fenêtre étroite ; la prochaine régénération ou le prochain PUT l'efface.
- Security surface touched: yes.
  - Validation d'entrée : `answer` limitée à 6000 caractères (422 testé, sans appel au service), `question_id` à 64.
  - Ségrégation : la question doit exister dans le kit de l'utilisateur courant (404 testé sur le kit d'un autre compte, document intact).
  - Quota : `require_user_quota` est vérifié avant tout appel.
  - La réponse est passée comme argument de `str.format`, jamais réinterprétée comme gabarit.
  - semgrep : `semgrep scan --config p/python --config p/secrets` sur `interview_prep.py`, `interview_prep_service.py`, `models.py` et `answer_feedback.md` donne 0 finding, 0 erreur.
- Verdict: ✅ DONE

## Execution Log
- 2026-10-23T20:23Z | claude-code | preflight | done | baseline logged in Notes
- 2026-10-23T20:23Z | claude-code | step 1 | started
- 2026-10-23T20:23Z | claude-code | step 1 | done | `pytest tests/test_interview_prep_models.py` 1 passed; `InterviewPrep.practice_attempts` = `List[PracticeAttempt]`
- 2026-10-23T20:23Z | claude-code | step 2 | started
- 2026-10-23T20:24Z | claude-code | step 2 | done | `grep -c "\[à chiffrer\]"` = 2; `template.format(...)` sans KeyError, exemple JSON rendu valide (`json.loads`)
- 2026-10-23T20:24Z | claude-code | step 3 | started
- 2026-10-23T20:26Z | claude-code | step 3 | done | `pytest tests/test_interview_prep_service.py` 15 passed (3 `test_practice_*` + température à 5 appels, 3 paramètres)
- 2026-10-23T20:26Z | claude-code | step 4 | started
- 2026-10-23T20:27Z | claude-code | step 4 | done | `pytest tests/test_interview_prep_api.py` 11 passed (3 `test_practice_*`)
- 2026-10-23T20:27Z | claude-code | step 5 | started
- 2026-10-23T20:28Z | claude-code | step 5 | done | `pytest tests/test_interview_prep_api.py` 13 passed (`cleared_when_questions_regenerated`, `kept_for_remaining_questions_on_update`)
- 2026-10-23T20:28Z | claude-code | step 6 | started
- 2026-10-23T20:30Z | claude-code | step 6 | done | DoD relancé : ruff exit 0 ; pytest 29 passed ; `-k practice` 8 passed ; orphelins 2 passed ; greps 5/1/6/2/1 ; `openapi.json` HTTP 200, `interview-prep/practice` = 1 ; diff relu ; semgrep 0 finding
- 2026-10-23T20:30Z | claude-code | close | done | status: done

## Notes
- Conventions lues : `CLAUDE.md` (identique à `AGENTS.md` et `GEMINI.md` : graphe code-review-graph, directives de tests) et `.cursorrules` (graphe seul). Aucune ne contredit le plan.
- Baseline (avant modification, 20:23Z) :
  - ruff exit 0 ;
  - pytest sur les 3 fichiers : 21 passed ;
  - `model=DEFAULT_INTERVIEW_MODEL` = 4, `"sub_action": "practice"` = 0, `require_user_quota(...)` = 5, `max_length=6000` = 0 ;
  - `openapi.json` : `interview-prep/practice` = 0.
- Choix de construction (les miens, l'utilisateur a passé le cadrage) :
  - **Modèle** : `DEFAULT_INTERVIEW_MODEL`, comme le reste du kit, et non un Flash dédié comme annoncé au départ. En local, c'est GPT-6.1 Sol. Estimation : environ 3 k tokens en entrée et 1 k en sortie, soit à peu près 0,015 $ par réponse notée, contre environ 0,002 $ avec Flash. Flash invente des chiffres, ce qui est le pire défaut pour une « version retravaillée ». Passer à Flash reste possible via `INTERVIEW_PREP_MODEL`, mais cela change tout le kit.
  - Le profil complet n'est pas envoyé au modèle. La version retravaillée doit se limiter à la réponse et à l'histoire liée, et le prompt coûte moins cher.
  - Note globale : moyenne serveur des 4 critères. Elle est déterministe et comparable d'une tentative à l'autre, pour suivre la progression.
  - Historique non plafonné (quelques Ko par tentative, loin de la limite de 16 Mo d'un document).
- Décision de l'utilisateur (23/10) : pas d'essai orphelin en base. Régénérer les questions efface l'historique d'entraînement, et le frontend le dit dans la confirmation (plan `20261023-interview-practice-panel-ui`). Même logique que les liens vers des histoires disparues, remis à `None`.
- Étape 4 : `test_practice_unknown_question_returns_404` vérifie aussi qu'une réponse de 6001 caractères est refusée en 422 sans appel au service (validation d'entrée).
- Étape 5 : le PUT retire les essais orphelins par un `$pull` (`question_id` `$nin` les id restants) dans la même mise à jour, et non par relecture puis réécriture. Un essai enregistré entre-temps n'est donc pas perdu. Le test vérifie aussi qu'un PUT sur un kit inexistant (upsert) passe.
