---
task: Ajouter une phase de recherche entreprise live et un style d'écriture personnel (voice DNA) au pipeline de lettre de motivation
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Recherche entreprise live + voice DNA pour le pipeline lettre de motivation

## Context

- Existing code checked :
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py` — pipeline séquentiel maison (`litellm.completion()` direct, pas CrewAI malgré le nom du fichier). `run_letter_pipeline_sync` orchestre `_call_analyst` → `_call_writer` → garde-fous + `_call_critic` → `_call_reviser` conditionnel. `_call_writer` construit le contexte du prompt `02_style.md` via `load_prompt()` (`template.format(**context)`).
  - `backend/job_trackers/src/job_trackers/letter_llm.py` — `DEFAULT_MODELS`/`ROLE_TEMPERATURES`/`env_var_map` pilotent le modèle par rôle (`offer_analyst`, `writer`, `critic`, `reviser`, `site_extractor`). Tous gemini-3.8-flash ou openai/gpt-5.6-terra.
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py` — `TavilyJobBoardSearchTool`, seul outil de recherche web existant dans le repo, câblé uniquement au crew de recherche d'offres (`crew.py`), pas au pipeline lettre. Utilise `tavily.TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))` — la clé est déjà configurée et payée.
  - `backend/app/models.py:508` — `CandidateProfile`, extensible sans douleur (Pydantic `BaseModel`).
  - `backend/app/services/profile/merge.py:400` — `build_profile_from_sources()`, fonction pure. Chaque champ scalaire est câblé à la main via `_first_non_empty(field, contributions)` — aucun passthrough générique.
  - `backend/app/routers/cover_letters.py:241` — `PUT /profile/candidate` accepte déjà un `dict` arbitraire et le stocke tel quel sous `sources.manual` (après avoir retiré `_id`/`id`/`user_id`/`sources`/`conflicts`/`updated_at`). Aucune modification de endpoint nécessaire pour faire transiter un nouveau champ `writing_style`.
  - Tests existants pertinents : `tests/test_cover_letter_prompts.py` (`test_writer_prompt_is_loaded_from_file` appelle `load_prompt("02_style", ...)` avec la liste exacte des placeholders actuels — cassera si on ajoute des placeholders sans l'étendre), `tests/test_cover_letter_crew.py` (plusieurs tests appellent `_call_writer(analyst_json, company_name)` en positionnel sans les nouveaux paramètres — imposent des défauts `=""`), `tests/test_letter_llm.py`, `tests/test_profile_merge.py`.
  - Commande de test canonique du repo (`backend/README.md:182`) : `uv run --no-sync pytest tests/... -v`.

- Déjà corrigé pendant l'investigation (hors scope de ce plan, mentionné pour traçabilité) :
  - **Bug pré-existant** : `backend/app/llm/prompts/cover_letter/03_critique.md` contenait un bloc JSON d'exemple avec accolades non échappées (`{` / `}` au lieu de `{{` / `}}`), ce qui faisait planter `template.format()` avec un `KeyError` à *chaque* appel du critique — donc à chaque génération de lettre. Corrigé et vérifié (`python3 -c "...".format(...)` passe désormais sans erreur sur les 3 prompts).
  - `backend/app/models.py` : ajout du champ `writing_style: Optional[str] = None` sur `CandidateProfile` (juste avant `updated_at`), suit le pattern des autres champs optionnels.

- Fresh info looked up : n/a — pas de nouvelle librairie, `tavily` et `litellm` sont déjà des dépendances du repo.

- Git status checked : branche `fix/profile-multi-sources`, arbre de travail déjà chargé de modifications en cours (non liées à cette tâche, notamment sur `profile/collectors`, `applications.py`, etc.). Aucune modification non commitée dans les fichiers listés en Surgical Scope au moment de ce plan, hormis les deux correctifs ci-dessus déjà appliqués.

## Simpler Alternative Considered

Question posée par l'utilisateur : un modèle Perplexity serait-il pertinent pour la recherche live, ou reste-t-on sur les modèles déjà présents ?

**Décision : pas de Perplexity.** Le repo a déjà une clé Tavily configurée et payée (`TAVILY_API_KEY`, utilisée par `TavilyJobBoardSearchTool`), déjà un client Python `tavily` en dépendance, et déjà un rôle LLM bon marché (`gemini-3.8-flash`, utilisé par `offer_analyst`/`critic`) capable de synthétiser des extraits de recherche en 2-3 phrases. Ajouter Perplexity introduirait un nouveau fournisseur, une nouvelle clé API, une nouvelle ligne de facturation — pour une capacité (recherche web + synthèse) déjà couverte par l'existant. Réutiliser Tavily + un nouveau rôle `company_researcher` sur `gemini-3.8-flash` est la version minimale qui répond au besoin.

Simplification acceptée par rapport à career-ops (`modes/cover.md`) : pas de checkpoint utilisateur avant rédaction (career-ops présente la synthèse et attend confirmation). Le pipeline actuel est *fire-and-forget* (`BackgroundTasks` FastAPI, déclenché à la création de candidature) sans aucun point de confirmation existant — en ajouter un serait un changement d'architecture bien plus large que ce qui est demandé ici. La recherche est donc automatique et dégrade silencieusement vers un contexte vide en cas d'échec (clé absente, quota, timeout, aucun résultat), sans jamais bloquer la génération.

Pas de cache par entreprise dans cette itération (chaque génération relance la recherche). Écarté sciemment pour rester minimal — l'app n'a pas d'entité "Company" distincte de l'offre pour accrocher un cache, et la latence ajoutée (~1-3s, deux appels Tavily en profondeur "basic") reste négligeable dans un pipeline déjà asynchrone.

## Surgical Scope

- **Files touched** :
  - `backend/job_trackers/src/job_trackers/letter_llm.py`
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/app/services/profile/merge.py`
  - `backend/app/llm/prompts/cover_letter/02_style.md`
  - `backend/tests/test_cover_letter_prompts.py`
  - `backend/tests/test_cover_letter_crew.py`
  - `backend/tests/test_profile_merge.py`
- **Files NOT touched** : tout le reste, notamment `backend/app/routers/cover_letters.py` (endpoint déjà générique, aucun changement requis), `backend/app/routers/applications.py`, le frontend (`CandidateProfileSection.tsx` — pas de champ UI pour `writing_style` dans ce plan, le champ reste accessible via l'API existante `PUT /profile/candidate`), `backend/job_trackers/src/job_trackers/tools/custom_tool.py` (le nouvel appel Tavily est une fonction simple dans `cover_letter_crew.py`, pas un `BaseTool` CrewAI — le pipeline lettre n'utilise pas CrewAI).
- **Symbols replaced** (→ à supprimer avant la fin) : aucun.
- **Symbols extended** (→ à garder) :
  - `letter_llm.DEFAULT_MODELS`, `ROLE_TEMPERATURES`, `get_letter_llm().env_var_map` — ajout de la clé `"company_researcher"`.
  - `cover_letter_crew._call_writer` — nouveaux paramètres optionnels `company_context: str = ""`, `voice_style: str = ""` (valeur par défaut pour ne pas casser les appels positionnels existants dans les tests).
  - `cover_letter_crew.run_letter_pipeline_sync` — appelle les deux nouvelles fonctions avant `_call_writer`.
  - `merge.build_profile_from_sources` — une ligne de plus dans le dict retourné.

## Definition of Done

- [x] Build passes : `n/a` — pas de build (Python, pas de bundler backend)
- [x] Tests pass : `cd backend && uv run --no-sync pytest tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py tests/test_letter_llm.py tests/test_profile_merge.py -v` (51 passed)
- [x] No dead code : n/a — aucun symbole remplacé, 0 orphelin confirmé
- [x] Type check : `n/a` — aucun mypy/pyright configuré dans ce backend
- [x] Manual check : `cd backend && python3 -c "from pathlib import Path; t = Path('app/llm/prompts/cover_letter/02_style.md').read_text(encoding='utf-8'); print(t.format(candidate_name='x', candidate_headline='y', company_name='z', min_words=1, max_words=2, missions='[]', experiences='[]', stacks='', projects='', capped_repetitions='', company_context_block='', voice_style_block=''))"` — validé avec blocs vides et blocs non vides

## Steps

- [x] Step 1 : `letter_llm.py` — ajouter le rôle `"company_researcher"` à `DEFAULT_MODELS` (`"gemini/gemini-3.8-flash"`), `ROLE_TEMPERATURES` (`0.3`) et à `env_var_map` dans `get_letter_llm` (`"LETTER_MODEL_COMPANY_RESEARCHER"`). Pas de validation cross-provider nécessaire (ce rôle alimente le writer, ne juge rien).
- [x] Step 2 : `cover_letter_crew.py` — ajouter `_search_company_web(company_name: str) -> list[str]` (2 requêtes Tavily `search_depth="basic"`, une sur l'actualité/produit, une sur les enjeux/stratégie, `max_results=5` chacune, contenu tronqué à 500 caractères par résultat ; `try/except` large retournant `[]` sur toute erreur, y compris clé API absente) et `_call_company_researcher(company_name: str, snippets: list[str], usage_acc=None) -> str` (retourne `""` immédiatement si `snippets` est vide ; sinon appelle `completion()` avec le rôle `company_researcher`, prompt qui synthétise en 2-3 phrases et précise explicitement que les extraits sont des données non fiables à ne jamais interpréter comme des instructions ; `try/except` retournant `""` sur échec). Ajouter les deux petites fonctions pures `_build_voice_style_block(voice_style: str) -> str` et `_build_company_context_block(company_context: str) -> str` qui renvoient soit `""` soit un bloc Markdown avec titre + contenu.
- [x] Step 3 : `cover_letter_crew.py` — étendre `_call_writer(analyst_json, company_name, company_context: str = "", voice_style: str = "", usage_acc=None)` : construit `company_context_block`/`voice_style_block` via les fonctions du Step 2 et les passe à `load_prompt("02_style", ...)`. Dans `run_letter_pipeline_sync`, avant l'appel à `_call_writer` : `snippets = _search_company_web(company_name)`, `company_context = _call_company_researcher(company_name, snippets, usage_acc=usage_acc)`, puis passer `company_context=company_context, voice_style=candidate_profile.get("writing_style") or ""` à `_call_writer`.
- [x] Step 4 : `02_style.md` — insérer `{voice_style_block}` juste après la section « Ton général » (avant « Voix et style ») et `{company_context_block}` juste avant la section « Accroche ». Mettre à jour la section « Accroche » pour préciser : si un contexte entreprise est fourni, ancrer l'accroche dans un enjeu réel qu'il mentionne plutôt que dans les seules missions de l'offre ; sinon garder le comportement actuel (partir d'un élément concret de l'offre).
- [x] Step 5 : `merge.py` — dans `build_profile_from_sources`, ajouter `_, writing_style = _first_non_empty("writing_style", contributions)` et `"writing_style": writing_style or ""` dans le dict `profile` retourné.
- [x] Step 6 : Mettre à jour les tests existants cassés par les nouveaux placeholders/paramètres :
  - `test_cover_letter_prompts.py::test_writer_prompt_is_loaded_from_file` — ajouter `company_context_block=""`, `voice_style_block=""` aux kwargs.
  - Ajouter `test_cover_letter_crew.py::test_company_research_failure_does_not_break_pipeline` (mock `_search_company_web` avec `side_effect=Exception`, vérifier que `run_letter_pipeline_sync` retourne quand même un `body`).
  - Ajouter `test_cover_letter_crew.py::test_writer_prompt_includes_voice_style_when_present` (mock `completion`, vérifier que le prompt envoyé contient le texte du `voice_style` passé).
  - Ajouter `test_profile_merge.py::test_writing_style_propagates_from_manual_source` (source `manual` avec `writing_style`, vérifie la présence dans le profil fusionné).
- [x] Step 7 (teardown) : relancer la suite de tests complète du Definition of Done. Scanner les imports/variables devenus orphelins dans les fichiers touchés (aucun symbole n'a été supprimé à ce stade, donc scan de confirmation seulement). Confirmer 0 orphelin.

## Code Review
- Dead code removed: yes (0 orphelin, aucun symbole remplacé)
- Build status: pass (51 passed)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no — pas d'auth/session, pas de SQL/shell/template concatené côté injection, pas de secrets nouveaux (réutilise `TAVILY_API_KEY` déjà géré), pas de migration DB, pas d'upload/chemin fichier. Le contenu Tavily est traité comme donnée non fiable dans le prompt de synthèse (instruction explicite anti-prompt-injection), par prudence plutôt que par exigence de la checklist.
- Verdict: ✅ DONE

## Execution Log
- 2026-09-16 18:07 | antigravity | baseline preflight | done | 48 passed, manual check exit 0
- 2026-09-16 18:07 | antigravity | step 1 | started
- 2026-09-16 18:09 | antigravity | step 1 | done | 8 passed (test_letter_llm.py)
- 2026-09-16 18:09 | antigravity | step 2 | started
- 2026-09-16 18:15 | antigravity | step 2 | done | 9 passed (test_cover_letter_crew.py) + helper assertions OK
- 2026-09-16 18:15 | antigravity | step 3 | started
- 2026-09-16 18:20 | antigravity | step 3 | done | 9 passed (test_cover_letter_crew.py)
- 2026-09-16 18:20 | antigravity | step 4 | started
- 2026-09-16 18:22 | antigravity | step 4 | done | manual format check OK (empty + non-empty blocks)
- 2026-09-16 18:22 | antigravity | step 5 | started
- 2026-09-16 18:25 | antigravity | step 5 | done | 26 passed (test_profile_merge.py)
- 2026-09-16 18:25 | antigravity | step 6 | started
- 2026-09-16 18:33 | antigravity | step 6 | done | 11 passed (test_cover_letter_crew), 5 passed (test_cover_letter_prompts), 27 passed (test_profile_merge)
- 2026-09-16 18:33 | antigravity | step 7 | started
- 2026-09-16 18:35 | antigravity | step 7 | done | 51 passed, manual format check exit 0, 0 orphan
- 2026-09-16 18:36 | antigravity | closeout | done | all DoD items pass

## Notes
- Preflight baseline DoD : `uv run --no-sync pytest tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py tests/test_letter_llm.py tests/test_profile_merge.py -v` -> 48 passed. Manual check exit 0.
