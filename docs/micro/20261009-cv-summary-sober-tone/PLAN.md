---
task: Rendre l'accroche des CV adaptés sobre et courte au lieu de prétentieuse
description: Tailored CV professional_summary too pretentious (fort de, expérience avérée, rigoureux, habitué à, employer names); tailor_prompt.md directive 3 rewritten with 45-word cap, banned self-praise qualifiers and inflating adjectives, no employer names; persona "expert mondial" and JSON placeholder "Accroche percutante" replaced; LLM gemini-3.8-flash eval script; pytest test_cv_tailor
status: done
created: 2026-10-09
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Accroche des CV : sobre et courte

## Context
- Existing code checked: `backend/app/llm/prompts/cv/tailor_prompt.md` (chargé par `cv_tailor.load_tailor_prompt`). La directive 3 demande déjà un ton « sobre » mais : persona l.1 « expert mondial en recrutement exécutif » ; modèle JSON « Accroche percutante de 3-4 lignes » qui contredit la directive ; interdits limités à « expert, passionné, leader visionnaire » ; « Souligne les accomplissements réels et la proposition de valeur » pousse à l'autopromotion. Tests du prompt : `backend/tests/test_cv_tailor.py` (assertions sur le contenu du prompt, l.191-243).
- Fresh info looked up: n/a — texte de prompt. Modèle en prod : `CV_TAILOR_MODEL` = gemini/gemini-3.8-flash.
- Git status checked: fichiers du périmètre propres ; correctif des dates (plan 20261009-cv-experience-dates-month-year) et sweep d'archive non commités, hors périmètre.
- Baseline mesurée (scratchpad/summary_eval.py, profil réel `scripts/candidate_profile_bakeoff.json`, offre Data Scientist santé fictive, 3 appels) : 51-59 mots, moyenne 56 ; « fort d'expériences », « doté d'une expérience avérée », « Rigoureux et habitué à », « Compétent dans », employeurs cités entre parenthèses.

## Simpler Alternative Considered
Ajouter seulement des mots à la liste d'interdits existante. Insuffisant : le persona et le modèle JSON « percutante » tirent dans l'autre sens, et le modèle obéit fortement au gabarit de sortie. Les trois points sont corrigés dans le même fichier, sans toucher au code Python.

## Surgical Scope
- **Files touched**: `backend/app/llm/prompts/cv/tailor_prompt.md`, `backend/tests/test_cv_tailor.py`
- **Files NOT touched**: `cv_tailor.py`, `cv_guards.py`, modèles, gabarits HTML, frontend, tout le reste
- **Symbols replaced** (→ to delete before done): phrases « expert mondial en recrutement exécutif », « Accroche percutante », « proposition de valeur » dans le prompt
- **Symbols extended** (→ keep): directive 3 du prompt (writing_style, exigences `critical`, positionnement), directive 8 (habilitations citées dans l'accroche)

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "from app.services.cv_tailor import load_tailor_prompt"`
- [x] Tests pass: `cd backend && uv run pytest tests/test_cv_tailor.py tests/test_cv_guards.py -v`
- [x] Phrases remplacées absentes : `grep -c "expert mondial\|percutante\|proposition de valeur" backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [x] Limite de longueur dans le prompt : `grep -c "45 mots" backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 2 (directive + modèle JSON)
- [x] Accroches réelles plus courtes : `cd backend && uv run python <scratchpad>/summary_eval.py 3` → moyenne ≤ 45 mots (baseline 56)
- [x] Accroches réelles sans vocabulaire ronflant ni employeur : même commande → « total ronflants: 0 » (baseline 3, liste élargie)
- [x] Type check: n/a — pas de type checker configuré pour le backend
- [x] Manual check: lecture des 3 accroches générées après correction, recopiées dans `## Notes`

## Steps
- [x] Step 1: Ajouter à `test_cv_tailor.py` un test sur le prompt (45 mots, interdits, absence de « percutante » / « expert mondial ») ; le lancer, constater l'échec (RED).
- [x] Step 2: Dans `tailor_prompt.md` : persona l.1 neutre, directive 3 réécrite (2-3 phrases, 45 mots max, ton de présentation orale, contenu = métier + domaine + actions concrètes liées à l'offre, interdits : autoqualificatifs, adjectifs qui gonflent, noms d'employeurs), modèle JSON « Accroche sobre de 2-3 phrases, 45 mots maximum ».
- [x] Step 3: Lancer `test_cv_tailor.py` et `test_cv_guards.py` ; tout vert.
- [x] Step 4: Lancer `summary_eval.py 3` (3 appels gemini-3.8-flash) ; vérifier moyenne ≤ 45 mots et 0 ronflant ; recopier les accroches dans `## Notes`.
- [x] Step 5 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the replaced symbols. Confirm 0 orphans.

## Code Review
- Dead code removed: yes — « expert mondial », « Accroche percutante », « proposition de valeur » retirés de tailor_prompt.md (0 occurrence) ; aucune fonction Python remplacée
- Build status: pass — import `load_tailor_prompt` exit 0
- Type errors: none (pas de type checker)
- Unintended side effects: none — seul le texte du prompt CV change ; directives 4-9, schéma JSON et garde d'honnêteté intacts ; 1er jet passé au « je », corrigé dans la même étape (Notes)
- Security surface touched: no — fichier de prompt et test, aucune entrée utilisateur nouvelle ni secret
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-09T22:00Z | claude-code | preflight | done | baseline: import exit 0 ; pytest test_cv_tailor + test_cv_guards 12 passed ; grep anciennes phrases 3 ; grep « 45 mots » 0 ; eval 56 mots moyen, 3 ronflants
- 2026-10-09T22:00Z | claude-code | step 1 | started
- 2026-10-09T22:01Z | claude-code | step 1 | done | RED attendu : `pytest -k short_sober` 1 failed sur `assert "expert mondial" not in prompt`
- 2026-10-09T22:01Z | claude-code | step 2 | started
- 2026-10-09T22:02Z | claude-code | step 2 | done | import exit 0 ; `pytest -k short_sober` 1 passed ; grep anciennes phrases 0 ; grep « 45 mots » 2
- 2026-10-09T22:02Z | claude-code | step 3 | started
- 2026-10-09T22:02Z | claude-code | step 3 | done | `pytest tests/test_cv_tailor.py tests/test_cv_guards.py` 13 passed
- 2026-10-09T22:02Z | claude-code | step 4 | started
- 2026-10-09T22:03Z | claude-code | step 4 | note | 1er essai : 41,7 mots, 0 ronflant, mais accroche passée au « je » (effet de « de vive voix ») ; consigne de ton reformulée, style impersonnel sans « je » — voir Notes
- 2026-10-09T22:04Z | claude-code | step 4 | done | `summary_eval.py 3` moyenne 39,0 mots, total ronflants 0, style impersonnel ; pytest 13 passed après ajustement
- 2026-10-09T22:04Z | claude-code | step 5 | started
- 2026-10-09T22:04Z | claude-code | step 5 | done | grep anciennes phrases dans tailor_prompt.md 0 ; occurrences restantes de « percutante » / « proposition de valeur » dans les prompts d'entretien et le frontend, fonctionnalités distinctes, hors périmètre
- 2026-10-09T22:05Z | claude-code | close-out | done | DoD rejouée : import exit 0 ; 134 passed (tailor, guards, templates, pdf) ; anciennes phrases 0 ; « 45 mots » 2 ; eval 39 mots / 0 ronflant ; diff lu (prompt +8 −4, test +14)

## Notes
- Conventions lues : CLAUDE.md (= AGENTS.md = GEMINI.md), .cursorrules. Baseline DoD dans l'Execution Log (preflight).
- Validation : l'utilisateur a demandé la correction puis la mise en production dans le même message ; exécution enchaînée sans validation séparée du plan.
- Le script d'évaluation vit hors dépôt (scratchpad de session) : il appelle le LLM réel, il ne doit pas entrer dans la suite de tests par défaut.
- Écart corrigé à l'étape 4 : la consigne « comme le candidat se présenterait de vive voix » faisait écrire « Je conçois… », incohérent avec le reste du CV (puces impersonnelles). Remplacée par « Ton : celui d'une personne qui décrit simplement son travail… Style impersonnel des CV, sans « je » ». Fichier déjà dans le périmètre.
- Accroches générées après correction (gemini-3.8-flash, offre Data Scientist santé fictive) :
  1. (42 mots) « Data Scientist avec expérience dans le secteur de la santé et de la recherche clinique. Développement de modèles et fiabilisation de pipelines de données avec Python et SQL. Traitement de dossiers patients et conception de tableaux de bord pour les équipes soignantes. »
  2. (37 mots) « Data Scientist intervenant sur les données de santé et les flux analytiques. Développe des pipelines d'intégration de données cliniques en Python et SQL, et conçoit des indicateurs et modèles pour les équipes médicales et de recherche. »
  3. (38 mots) « Data Scientist intervenant sur les données cliniques et de santé. Conception de flux d'intégration de données en Python et SQL, développement de modèles NLP et restitution d'indicateurs via des tableaux de bord pour les équipes médicales. »
