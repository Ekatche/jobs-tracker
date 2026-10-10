---
task: Lettre de motivation — fil narratif ancré dans le sujet de l'offre, plus de leçons inventées, formations visibles
description: cover letter story incoherent (abstract thesis "incertitude/interprétabilité" imposed on real projects, invented lessons "m'a appris que / m'a montré que" after each project, education never sent to analyst) — cover_letter_crew.py _call_analyst education/certifications facts + grounded guiding_thesis/career_thread prompt, 02_style.md retained-fact rule and {education} block, 03_critique.md invented-lesson flaw, 04_revision.md fix, letter_guards.py max_lesson_formulas + education entities allowlist
status: done
created: 2026-10-10
---

# Lettre de motivation — fil narratif ancré, pas de leçon inventée, formations visibles

## Context
- Existing code checked:
  - Lettre prod du 2026-10-10 (offre Indeed 7a351a5d0466b59c, plasticité tumorale) : tous les faits cités existent dans le profil (confirmé par l'utilisateur), mais le récit est incohérent. La thèse retenue (« incertitude et interprétabilité ») est un thème abstrait importé de l'offre ; chaque projet est ensuite tordu pour « enseigner » ce thème (« La réduction de dimensionnalité et l'analyse de survie m'ont appris à ne pas dissocier la performance d'un modèle de la lecture… », « …m'a montré que la fiabilité d'une analyse tient aussi à un code structuré… »). Le lien réel — formation à l'analyse multi-omique, projets sur l'expression des gènes et la réponse/résistance à l'immunothérapie, DeepOS — n'est pas raconté.
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py:131-155` (prompt analyste) : consigne 2 « idée directrice… tirée du métier du candidat » et consigne 3 « synthèse thématique » ne demandent nulle part que la thèse repose sur un recouvrement concret (domaine, données, méthodes) entre l'offre et des faits nommés du candidat. `career_thread` ne nomme pas les faits à raconter.
  - `cover_letter_crew.py:108-143` : l'analyste reçoit `experiences` et `projects`, jamais `education` ni `certifications` (`CandidateProfile.education`, `models.py:605` ; `CandidateEducation` = school, degree, years, topics ; `CandidateCertification` = name, issuer, year, topics). Une formation en analyse multi-omique est donc invisible. `merge.py:488` applique déjà `excluded_education` au profil fusionné : rien à filtrer ici.
  - `backend/app/llm/prompts/cover_letter/02_style.md:42` exemple « Ce projet m'a appris à... » ; `:110` « ce que le candidat en a retenu » ; `:153` « ce qu'il en a retenu » ; `:218` « ce qu'il a appris de cette expérience ». Aucune contrainte sur la nature du « retenu » : le modèle fabrique une morale qui colle à l'offre. Bloc « Faits autorisés » (`:280-293`) : missions, expériences, outils, projets — pas de formations.
  - `03_critique.md:18-60` : défauts connus (CV déguisé, CV paraphrasé, absence d'idée directrice, écho…) — aucun défaut « leçon inventée » ni « fil rouge forcé ». `04_revision.md` § Faits : interdit d'ajouter expérience, techno, chiffre, résultat — pas de leçon.
  - `backend/app/services/letter_guards.py` : `_check_entities` autorise companies/stacks/projects/offer_terms/selected_projects — un nom d'école ou d'organisme certificateur serait rejeté ; aucun plafond sur les formules « m'a appris / m'a montré ».
  - `load_prompt` (`cover_letter_crew.py:75-82`) : `format_map(_SafePromptDict)` — un placeholder absent ne casse pas, un kwarg en plus non plus.
- Fresh info looked up: n/a — prompts et logique métier
- Git status checked: propre hors `docs/micro` (archive sweep de ce tour : deux plans `done` déplacés, INDEX réécrit ; non commités, hors périmètre)

## Simpler Alternative Considered
Ne toucher que `02_style.md` (interdire les leçons inventées). Insuffisant : la thèse abstraite vient de l'analyste, et la formation multi-omique n'atteint jamais le pipeline. Sans faits de formation et sans thèse ancrée, le rédacteur n'a pas la matière du vrai fil narratif. Écartée aussi : un champ `selected_facts` structuré imposant au rédacteur l'ordre des faits — mécanisme en plus, à n'ajouter que si la prose continue de dévier après ce plan.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `backend/app/llm/prompts/cover_letter/02_style.md`
  - `backend/app/llm/prompts/cover_letter/03_critique.md`
  - `backend/app/llm/prompts/cover_letter/04_revision.md`
  - `backend/app/services/letter_guards.py`
  - `backend/tests/test_cover_letter_crew.py`
  - `backend/tests/test_letter_guards.py`
- **Files NOT touched**: tous les autres ; `01_fond.md`, `models.py`, `merge.py`, routers, frontend
- **Symbols replaced** (→ to delete before done): exemple « Ce projet m'a appris à... » (`02_style.md:42`) ; consignes analyste 2-3 actuelles (`cover_letter_crew.py:134-135`) ; champ JSON `"career_thread": "Synthèse thématique liant le parcours…"` (`:153`)
- **Symbols extended** (→ keep): `_call_analyst` (faits `education`/`certifications`, prompt, clé `selected_education`), `_call_writer` (kwarg `education`), `_check_entities` (faits de formation autorisés), `evaluate_letter_guards` (check formules de leçon), `LETTER_RULES` (`max_lesson_formulas`), `PROMPT_VERSION` v8 → v9

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import sys; sys.path.insert(0, 'job_trackers/src/job_trackers'); import cover_letter_crew"`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cover_letter_crew.py tests/test_letter_guards.py tests/test_cover_letter_prompts.py -q` (base : 70 passed)
- [x] Analyste voit les formations : test `test_call_analyst_sees_education` vert (sujet de formation présent dans le prompt envoyé, `selected_education` renvoyé sans champ vide)
- [x] Rédacteur reçoit les formations : test `test_writer_prompt_includes_education` vert
- [x] Thèse ancrée : test `test_analyst_prompt_requires_grounded_thesis` vert (le prompt envoyé contient « nomme » et « recouvrement » et ne contient plus « Synthèse thématique liant le parcours »)
- [x] Leçons plafonnées : tests `test_repeated_lesson_formulas_are_flagged` (deux « m'a appris / m'a montré » → bloquant) et `test_single_lesson_formula_is_allowed` verts
- [x] Formations autorisées par les garde-fous : test `test_education_facts_are_allowed_entities` vert (nom d'école cité → aucune violation d'entité)
- [x] Exemple de leçon supprimé : `grep -c "Ce projet m'a appris" backend/app/llm/prompts/cover_letter/02_style.md` → 0
- [x] Critique et réviseur connaissent le défaut : `grep -c "Leçon inventée" backend/app/llm/prompts/cover_letter/03_critique.md backend/app/llm/prompts/cover_letter/04_revision.md` → ≥ 1 et ≥ 1
- [x] Bloc faits du rédacteur : `grep -c "{education}" backend/app/llm/prompts/cover_letter/02_style.md` → 1
- [x] No dead code: `grep -c "Synthèse thématique liant le parcours" backend/job_trackers/src/job_trackers/cover_letter_crew.py` → 0
- [x] Type check: n/a — pas de type checker configuré sur le backend
- [ ] Manual check: après déploiement, l'utilisateur régénère la lettre de l'offre Indeed 7a351a5d0466b59c et vérifie : le fil part de sa formation multi-omique et de ses projets sur l'expression des gènes / immunothérapie vers la plasticité tumorale ; aucune phrase « m'a appris que / m'a montré que » tirant une morale générale ; au plus une formule de ce type

## Steps
- [x] Step 1: Tests rouges d'abord — `test_cover_letter_crew.py` : `test_call_analyst_sees_education`, `test_writer_prompt_includes_education`, `test_analyst_prompt_requires_grounded_thesis` ; `test_letter_guards.py` : `test_repeated_lesson_formulas_are_flagged`, `test_single_lesson_formula_is_allowed`, `test_education_facts_are_allowed_entities`. Lancer, constater l'échec.
- [x] Step 2: `cover_letter_crew.py` — `_call_analyst` : `education_facts` = éducation (school, degree, years, topics) + certifications (name, issuer, year, topics), champs vides omis ; bloc « Formations du candidat » dans le prompt ; consignes 2-3 réécrites : la thèse est le recouvrement concret (domaine, données, question scientifique ou métier, méthodes) entre le sujet de l'offre et des faits nommés du candidat ; interdit : un thème abstrait de l'offre qu'aucun fait du candidat ne démontre ; `career_thread` nomme les 2-3 faits (formation, projet, expérience) à raconter et le lien factuel entre eux et le sujet de l'offre, dans l'ordre où la lettre les racontera ; champ JSON `career_thread` reformulé ; clé `selected_education` renvoyée. `_call_writer` : `education=json.dumps(selected_education)`. `PROMPT_VERSION` → v9.
- [x] Step 3: `02_style.md` — `:42` remplacer l'exemple par une entrée factuelle (« Sur ce projet, le modèle… ») ; après `:110` et `:153`/`:218` : « ce que le candidat en a retenu » est un fait du projet (résultat obtenu, difficulté rencontrée, choix fait) présent dans les faits fournis, jamais un principe général ni un mot de l'offre ; une seule formule « m'a appris / m'a montré » dans toute la lettre ; le lien avec le poste est le sujet lui-même (mêmes données, même question), dit simplement ; bloc « Faits autorisés » : ajouter « Formations :\n{education} ».
- [x] Step 4: `03_critique.md` — dans « Vérifie aussi » : « Leçon inventée : une phrase “m'a appris / m'a montré / m'ont appris” dont le contenu est un principe général ou reprend le vocabulaire de l'offre au lieu d'un fait du projet raconté » et « Fil rouge forcé : les projets racontés sont pliés à un thème abstrait au lieu de partager le sujet du poste ». `04_revision.md` — § Faits : « aucune leçon ou conclusion qui ne soit un fait du JSON » ; consigne : « Si le critique signale une Leçon inventée, remplace-la par le fait du projet ou supprime la phrase ».
- [x] Step 5: `letter_guards.py` — `LETTER_RULES["max_lesson_formulas"] = 1` ; check : occurrences de `m'(a|ont) (appris|montré|enseigné)` (casse ignorée, apostrophes droite et typographique) > 1 → violation « Leçons tirées en excès… » ; `_check_entities` : texte de chaque `selected_education` (school, degree, name, issuer, topics) autorisé, séparateurs `(),|` neutralisés.
- [x] Step 6: Lancer la suite du DoD, vérifier 70 + 6 tests verts.
- [x] Step 7 (teardown): supprimer l'exemple « Ce projet m'a appris à... » et l'ancienne consigne « Synthèse thématique liant le parcours » ; scan d'orphelins borné à ces chaînes (greps du DoD) ; 0 orphelin.

## Code Review
- Dead code removed: yes — « Ce projet m'a appris à... » retiré de `02_style.md`, « Synthèse thématique liant le parcours » retiré de `cover_letter_crew.py` ; les seules occurrences restantes sont l'assertion négative `test_cover_letter_crew.py:663` et la fixture `test_letter_guards.py:387`
- Build status: pass — `import cover_letter_crew` OK
- Type errors: none (n/a, pas de type checker ; diagnostic IDE « Could not find name `_education_text` » transitoire pendant l'édition, résolu — 34 tests garde-fous verts)
- Unintended side effects: none — diff relu hunk par hunk ; `selected_education` est une clé additive du JSON analyste (le réviseur la reçoit par `json.dumps` du JSON complet, les anciens JSON sans la clé restent valides via `.get`)
- Security surface touched: no (prompts LLM et garde-fous de contenu, aucune entrée utilisateur interpolée dans du SQL/shell)
- Verdict: ✅ DONE — manual check à faire par l'utilisateur après déploiement (lettre 7a351a5d0466b59c)

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-10T11:56Z | claude-code | step 1 | started
- 2026-10-10T11:59Z | claude-code | step 1 | done | `uv run pytest tests/test_cover_letter_crew.py tests/test_letter_guards.py -q` 66 passed, 5 failed (les 5 nouveaux attendus rouges ; `test_single_lesson_formula_is_allowed` vert par construction)
- 2026-10-10T11:59Z | claude-code | step 2 | started
- 2026-10-10T12:01Z | claude-code | step 2 | done | `uv run pytest tests/test_cover_letter_crew.py -q` 36 passed, 1 failed (`test_writer_prompt_includes_education`, attend `{education}` de l'étape 3)
- 2026-10-10T12:01Z | claude-code | step 3 | started
- 2026-10-10T12:02Z | claude-code | step 3 | done | `uv run pytest tests/test_cover_letter_crew.py tests/test_cover_letter_prompts.py -q` 42 passed ; grep "Ce projet m'a appris" 0 ; grep "{education}" 1
- 2026-10-10T12:02Z | claude-code | step 4 | started
- 2026-10-10T12:02Z | claude-code | step 4 | done | grep "Leçon inventée" 03_critique 1, 04_revision 1 ; 42 passed inclut test_cover_letter_prompts
- 2026-10-10T12:02Z | claude-code | step 5 | started
- 2026-10-10T12:03Z | claude-code | step 5 | done | `uv run pytest tests/test_letter_guards.py -q` 34 passed
- 2026-10-10T12:03Z | claude-code | step 6 | started
- 2026-10-10T12:03Z | claude-code | step 6 | done | IMPORT_OK ; `uv run pytest tests/test_cover_letter_crew.py tests/test_letter_guards.py tests/test_cover_letter_prompts.py -q` 76 passed (70 + 6) ; `-k "education or grounded_thesis or lesson_formula"` 6 passed
- 2026-10-10T12:06Z | claude-code | step 7 | started
- 2026-10-10T12:06Z | claude-code | step 7 | done | greps DoD : "Ce projet m'a appris" 02_style 0 ; "Leçon inventée" 03 1 / 04 1 ; "{education}" 1 ; "Synthèse thématique liant le parcours" crew 0 ; scan borné `backend/app backend/job_trackers/src backend/tests` : seules occurrences restantes = tests (crew:663 assertion négative, guards:387 fixture) — 0 orphelin
- 2026-10-10T12:07Z | claude-code | close out | done | DoD complet rejoué ; diff relu ; tests passés sans Mongo ; status: done

## Notes
- Conventions lues : `CLAUDE.md` racine (= `AGENTS.md`, `GEMINI.md`), `.cursorrules` — lus plus tôt dans la session (plan précédent). Règle tests : forte valeur, pas de sur-mocking ; aucune identité réelle dans prompts ou module.
- Baseline 2026-10-10T11:56Z : import OK ; 70 passed ; `grep -c "Ce projet m'a appris"` 1 ; `grep -c "Leçon inventée"` 0 et 0 ; `grep -c "{education}"` 0 ; `grep -c "Synthèse thématique liant le parcours"` 1. Les 6 tests nommés n'existent pas encore.
- Coût : prompt analyste et rédacteur grossissent du JSON des formations (quelques centaines de tokens). Le plafond de leçons ne déclenche une révision que si le rédacteur en écrit deux ou plus.
- Le critique ne voit toujours que missions + lettre : le défaut « Fil rouge forcé » est détecté sur la forme (projets pliés à un thème abstrait), pas par comparaison aux faits. Si cela ne suffit pas, passer `career_thread` au critique dans un plan suivant.
