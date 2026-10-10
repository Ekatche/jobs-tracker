---
task: Lettre de motivation — exploiter les projets du candidat et ne plus recopier l'intitulé du poste
description: cover letter pipeline ignore project descriptions (analyst never sees projects, writer gets names only) and copies long job_title verbatim — cover_letter_crew.py _call_analyst/_call_writer selected_projects, 02_style.md / 04_revision.md title wording, letter_guards.py verbatim title check + project facts allowlist (entities, numbers)
status: done
created: 2026-10-10
---

# Lettre de motivation — projets exploités, intitulé du poste reformulé

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py:111` — `projects = [p.get("name") ...]` : seuls les NOMS des projets sont gardés. Le prompt analyste (l.122-143) ne contient que `raw_exps` : l'analyste ne voit jamais les projets, donc `target_challenge` / `guiding_thesis` / `career_thread` sont bâtis sur les seules expériences. Le rédacteur (l.356) reçoit `projects=", ".join(noms)` : aucune description, aucun contexte. Les stacks de projets (l.113-120) ne sont pas ajoutées à `candidate_stacks`.
  - Présent depuis le premier commit du pipeline (c9c283d), jamais corrigé.
  - `backend/app/llm/prompts/cover_letter/02_style.md` (premier paragraphe) : « une phrase qui nomme le poste par son intitulé s'il est fourni » — ajouté dans cde0af9. Avec un intitulé Indeed de 11 mots en Title Case, le rédacteur le recopie tel quel.
  - `backend/app/llm/prompts/cover_letter/04_revision.md:33` : même consigne côté réviseur (« en le nommant par son intitulé, champ job_title »).
  - `backend/app/services/letter_guards.py` : `_check_entities` n'autorise que noms de projets + stacks d'expériences ; check 13 (chiffres) ne regarde que `selected_experiences`. Un projet raconté avec « Foundation Medicine » ou un chiffre de projet déclencherait une violation et le réviseur l'effacerait.
  - `CandidateProject` (`backend/app/models.py:536`) : name, description, stack, url, repo, year, context, highlights, sources.
  - Lettre prod du 2026-10-10 (offre Indeed 7a351a5d0466b59c) : intitulé recopié, aucun projet (survie multi-omique, lecteur PDF Foundation Medicine, pipeline NGS) cité. Lecture de la base prod refusée par le classifieur : diagnostic fait sur le code.
- Fresh info looked up: n/a — logique métier et prompts
- Git status checked: une autre session a laissé `docs/micro/INDEX.md` modifié et le rename d'archive du plan `20261010-cv-summary-grounded-in-experience` indexé (staged). Hors périmètre, non touché ; seule une ligne sera ajoutée en fin d'INDEX.md.

## Simpler Alternative Considered
Ne changer que les prompts (supprimer la consigne d'intitulé, ajouter « un projet compte comme une expérience »). Insuffisant : le rédacteur ne reçoit que des noms de projets, il n'a rien à raconter, et l'analyste continue à construire le fil rouge sans eux. Le changement de code dans `_call_analyst` / `_call_writer` est le minimum. Écartée aussi : une sélection de projets par l'analyste (nouveau champ JSON) — mécanisme en plus, à n'ajouter que si la lettre continue d'ignorer les projets.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/app/llm/prompts/cover_letter/02_style.md`
  - `backend/app/llm/prompts/cover_letter/04_revision.md`
  - `backend/app/services/letter_guards.py`
  - `backend/tests/test_cover_letter_crew.py`
  - `backend/tests/test_letter_guards.py`
- **Files NOT touched**: tous les autres ; `01_fond.md`, `03_critique.md`, `backend/scripts/letter_bakeoff.py` (déjà désynchronisé du rédacteur, hors sujet)
- **Symbols replaced** (→ to delete before done): passage `projects=", ".join(analyst_json.get("projects", []))` dans `_call_writer` ; consigne « nomme le poste par son intitulé » (02_style.md) et « en le nommant par son intitulé (champ job_title du JSON, s'il est renseigné) » (04_revision.md)
- **Symbols extended** (→ keep): `_call_analyst` (prompt + clé `selected_projects` + stacks de projets), `_call_writer`, `_check_entities` (faits de projets autorisés), `evaluate_letter_guards` (check chiffres + nouveau check intitulé recopié), `LETTER_RULES` (`max_verbatim_title_words`), `PROMPT_VERSION` v7 → v8. Clé `projects` (noms) conservée : consommée par `_check_entities`.

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import sys; sys.path.insert(0, 'job_trackers/src/job_trackers'); import cover_letter_crew"`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cover_letter_crew.py tests/test_letter_guards.py tests/test_cover_letter_prompts.py -q` (base : 65 passed)
- [x] Analyste voit les projets : test `test_call_analyst_sees_project_details` vert (description de projet présente dans le prompt envoyé, `selected_projects` renvoyé, stack de projet dans `stacks`)
- [x] Rédacteur reçoit le détail des projets : test `test_writer_prompt_includes_project_details` vert
- [x] Intitulé long recopié = violation, intitulé court = OK : tests `test_long_job_title_copied_verbatim_is_flagged` et `test_short_job_title_can_be_quoted` verts
- [x] Faits de projet autorisés par les garde-fous : test `test_project_facts_are_allowed_entities_and_numbers` vert
- [x] Consigne d'intitulé verbatim supprimée : `grep -c "par son intitulé" backend/app/llm/prompts/cover_letter/02_style.md backend/app/llm/prompts/cover_letter/04_revision.md` → 0 et 0
- [x] No dead code: `grep -c 'projects=", ".join' backend/job_trackers/src/job_trackers/cover_letter_crew.py` → 0
- [x] Type check: n/a — pas de type checker configuré sur le backend
- [ ] Manual check: après déploiement, l'utilisateur régénère la lettre de l'offre Indeed 7a351a5d0466b59c et vérifie : intitulé non recopié, au moins un projet (survie multi-omique, lecteur Foundation Medicine ou pipeline NGS) raconté

## Steps
- [x] Step 1: Tests rouges d'abord — ajouter dans `test_cover_letter_crew.py` `test_call_analyst_sees_project_details` et `test_writer_prompt_includes_project_details` ; dans `test_letter_guards.py` `test_long_job_title_copied_verbatim_is_flagged`, `test_short_job_title_can_be_quoted`, `test_project_facts_are_allowed_entities_and_numbers`. Lancer, constater l'échec.
- [x] Step 2: `cover_letter_crew.py` — `_call_analyst` : construire `project_facts` (name, context, year, description, stack, highlights ; sans url/repo/sources), ajouter les stacks de projets à `candidate_stacks`, injecter les projets dans le prompt analyste (consignes 2-3 : expériences ET projets), renvoyer `selected_projects`. `_call_writer` : `projects=json.dumps(selected_projects)`. `PROMPT_VERSION` → v8.
- [x] Step 3: `02_style.md` — premier paragraphe : désigner le poste comme à l'oral, intitulé court repris, intitulé de plus de six mots résumé à son métier, jamais ses majuscules ; « Angle spécifique sur l'expérience ou le projet pivot » ; dans « pertinence avant exhaustivité », un projet compte autant qu'une expérience quand il est plus proche de l'offre. `04_revision.md:33` : même règle d'intitulé.
- [x] Step 4: `letter_guards.py` — `LETTER_RULES["max_verbatim_title_words"] = 6` ; nouveau check : intitulé de plus de 6 mots retrouvé tel quel (séquence de mots, casse ignorée) → violation ; `_check_entities` et check 13 acceptent aussi les faits de `selected_projects` (nom, description, highlights, stack).
- [x] Step 5: Lancer la suite du DoD, vérifier 65 + 5 tests verts.
- [x] Step 6 (teardown): supprimer l'ancien passage `projects=", ".join(...)` et les consignes d'intitulé verbatim ; scan d'orphelins borné à ces symboles (greps du DoD) ; 0 orphelin.

## Code Review
- Dead code removed: yes — `projects=", ".join(...)` (0 occurrence), consignes « par son intitulé » (0 et 0) ; clé `projects` (noms) conservée, lue par `letter_guards.py:108`
- Build status: pass — import `cover_letter_crew` OK, `PROMPT_VERSION` v8
- Type errors: none — pas de type checker configuré
- Unintended side effects: none — le JSON analyste n'est ni renvoyé ni persisté (retour du pipeline : body, verdict, guard_report, models, usage) ; le réviseur reçoit tout le JSON analyste (l.459), donc les projets ; le critique ne voit que missions + lettre. Prompts analyste et rédacteur plus longs du JSON des projets (< 0,01 $/lettre)
- Security surface touched: no (prompts LLM et garde-fous de contenu, aucune entrée utilisateur interpolée dans du SQL/shell)
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-10T09:40Z | claude-code | step 1 | started
- 2026-10-10T09:43Z | claude-code | step 1 | done | 4 failed (assertions attendues : prompt sans description de projet, pas de violation d'intitulé, 'Foundation' rejeté), `test_short_job_title_can_be_quoted` vert (non-régression)
- 2026-10-10T09:43Z | claude-code | step 2 | started
- 2026-10-10T09:44Z | claude-code | step 2 | done | `pytest tests/test_cover_letter_crew.py` 34 passed (dont les 2 nouveaux) ; `grep -c 'projects=", ".join'` → 0
- 2026-10-10T09:44Z | claude-code | step 3 | started
- 2026-10-10T09:44Z | claude-code | step 3 | done | `grep -c "par son intitulé"` → 0 et 0 ; `pytest tests/test_cover_letter_prompts.py` 5 passed
- 2026-10-10T09:45Z | claude-code | step 4 | started
- 2026-10-10T09:47Z | claude-code | step 4 | done | `pytest tests/test_letter_guards.py` 31 passed (dont `test_long_job_title_copied_verbatim_is_flagged`, `test_project_facts_are_allowed_entities_and_numbers`)
- 2026-10-10T09:47Z | claude-code | step 5 | started
- 2026-10-10T09:47Z | claude-code | step 5 | done | `pytest test_cover_letter_crew test_letter_guards test_cover_letter_prompts` 70 passed (65 + 5)
- 2026-10-10T09:47Z | claude-code | step 6 | started
- 2026-10-10T09:48Z | claude-code | step 6 | done | `grep -c "par son intitulé"` 0 et 0 ; `grep -c 'projects=", ".join'` 0 ; `selected_projects` lu uniquement par crew + letter_guards
- 2026-10-10T09:49Z | claude-code | close | done | DoD rejoué : import OK, 70 passed, 5 tests nommés verts (aussi avec Mongo injoignable), greps 0/0/0 ; diff relu en entier

## Notes
- Conventions lues : `CLAUDE.md` racine (= `AGENTS.md`, `GEMINI.md`, contenu identique), `.cursorrules` (bloc code-review-graph). Règle tests : tests à forte valeur (gardes-fous IA `letter_guards`, logique métier), pas de sur-mocking.
- Baseline 2026-10-10T09:40Z : import `cover_letter_crew` OK ; `pytest test_cover_letter_crew test_letter_guards test_cover_letter_prompts` 65 passed ; `grep -c "par son intitulé"` 1 et 1 ; `grep -c 'projects=", ".join'` 1. Les 5 tests nommés n'existent pas encore.
- Coût : le prompt analyste et le prompt rédacteur grossissent du JSON des projets (quelques centaines à quelques milliers de tokens selon le nombre de projets collectés). À ~2 $/M tokens en entrée (GPT-6.1 Sol), l'ordre de grandeur est < 0,01 $ par lettre.
- Le nouveau check d'intitulé ne déclenche une révision (≈ un appel en plus) que si le rédacteur recopie quand même un long intitulé.
- Étape 4 : la stack des projets n'est pas dans `_project_text` : elle est déjà autorisée via `analyst_data["stacks"]`, alimenté par `_call_analyst` (boucle `exps + project_facts`).
- Étape 4 : `project.get("highlights") or []` plutôt que `.get("highlights", [])`, pour qu'un `highlights: None` ne fasse pas planter le dépaquetage.
- Clôture : les 5 tests ajoutés passent avec `MONGO_LOCAL_TEST_HOST=mongo.invalid` (aucun service requis).
- Reste : vérification manuelle (DoD) après commit, push et déploiement par l'utilisateur.
