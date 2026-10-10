---
task: Accroche des CV générale qui présente les apports du parcours, sans emprunter le vocabulaire de l'offre
description: Tailored CV professional_summary rewritten as general 3-sentence profile pitch (métier + types de travaux, outils + étendue de la chaîne de la donnée, apport aux équipes métiers), 70 words max, first person allowed after first sentence, "avec une expérience dans" instead of "spécialisé dans" (still forbidden), tools at end of sentence 2 ("principalement en"); summary written from profile only with self-review; offer only chooses which real strengths come first; forbids offer terms (method, domain, technology, deliverable, audience) not proven by profile and partial/missing Bloc B requirement wording; removed "guident la première phrase" and "Positionne le candidat" (cause of expert-sounding summaries borrowing modélisation statistique, multi-omiques); tailor_prompt.md directive 3; gemini-3.8-flash eval with Bloc B evaluation; pytest test_cv_tailor
status: done
created: 2026-10-10
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Accroche des CV générale, ancrée dans le parcours réel

## Context
- Existing code checked: `backend/app/llm/prompts/cv/tailor_prompt.md` directive 3 (réécrite la veille, plan archive/2026-10/20261009-cv-summary-sober-tone : 45 mots, impersonnel, « spécialisé dans » interdit). Exemple utilisateur encore « expert » : « Ingénieur en modélisation statistique et intelligence artificielle appliquée aux données biologiques et cliniques. Conception de modèles prédictifs multi-omiques, quantification de l'incertitude… » — vocabulaire de l'offre, absent du profil (`scripts/candidate_profile_bakeoff.json` : pipelines, OCR/NER, RAG, RCP moléculaire). Cause probable : `load_tailor_prompt` (`cv_tailor.py:50-71`) injecte en prod l'analyse Bloc B avec des exigences `partial_match`, et la consigne « Les exigences de poids `critical` … guident la première phrase de l'accroche » + « Positionne le candidat … par rapport au poste ciblé » font remonter l'intitulé de ces exigences dans l'accroche.
- Fresh info looked up: n/a — texte de prompt.
- Git status checked: clean.
- Forme voulue (redirection utilisateur 2026-10-10, après une première version « missions + type de structure ») : un texte **général** qui présente les apports du parcours, sur ce modèle donné par l'utilisateur : « Data Scientist spécialisé dans la conception de modèles de machine learning, de pipelines de données et de solutions analytiques sur le cloud. Expérimenté en Python, SQL, PySpark, j'interviens sur l'ensemble de la chaîne de valorisation de la donnée, de son intégration jusqu'à son exploitation à travers des modèles prédictifs, des tableaux de bord et des applications d'intelligence artificielle. Mon objectif est de transformer les données en leviers d'aide à la décision pour les métiers. » (≈ 70 mots, 3 phrases, « je » admis, « spécialisé dans » admis).
- Précision utilisateur (09:08) : pas de « spécialisé dans » ; la 1re phrase dit que le candidat a de l'expérience dans le domaine (« avec une expérience dans… »).
- Précision utilisateur (09:13, AskUserQuestion) : pas de « Avec Python, SQL et PySpark, » en tête de phrase 2 ; les outils passent en fin de phrase (« …, principalement en Python, SQL et PySpark »).
- Avant le passage en sobre (0d9fb36), l'accroche faisait 3 à 4 lignes : 70 mots reste dans ce gabarit.

## Simpler Alternative Considered
Ajouter « n'emprunte pas le vocabulaire de l'offre » à la directive actuelle. Insuffisant : la directive actuelle impose 45 mots impersonnels centrés sur des missions, l'inverse de la forme demandée, et les deux consignes qui poussent vers l'offre resteraient. On réécrit la directive 3, dans le même fichier, sans toucher au code Python.

## Surgical Scope
- **Files touched**: `backend/app/llm/prompts/cv/tailor_prompt.md`, `backend/tests/test_cv_tailor.py`
- **Files NOT touched**: `cv_tailor.py`, `cv_guards.py`, évaluateur Bloc B, gabarits, frontend, tout le reste
- **Symbols replaced** (→ to delete before done): phrases du prompt « Rédige 2 à 3 phrases courtes, 45 mots maximum… », « Ton : … Style impersonnel des CV, sans « je » », « Contenu : le métier et le domaine… », « Positionne le candidat avec exactitude… », « Les exigences de poids `critical` de l'analyse Bloc B guident la première phrase… », « 45 mots maximum » du schéma JSON
- **Symbols extended** (→ keep): directive 3 (writing_style, qualificatifs et adjectifs interdits restants, aucun nom d'employeur), directive 8 (habilitations dans l'accroche), tests `test_load_tailor_prompt_asks_for_short_sober_summary` et `test_load_tailor_prompt_grounds_summary_in_profile_experiences`

## Definition of Done
- [ ] Build passes: `cd backend && uv run python -c "from app.services.cv_tailor import load_tailor_prompt"`
- [ ] Tests pass: `cd backend && uv run pytest tests/test_cv_tailor.py tests/test_cv_guards.py tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -q`
- [ ] Consignes remplacées absentes : `grep -c "guident la première phrase\|Positionne le candidat\|Contenu : le métier\|45 mots\|sans « je »" backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [ ] Interdiction d'emprunt présente : `grep -c "N'emprunte à l'offre aucun terme" backend/app/llm/prompts/cv/tailor_prompt.md` → 1
- [ ] Formulation « expérience » au lieu de « spécialisé » : `grep -c "avec une expérience dans" backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 2 (consigne + exemple) ; `grep -c "Scientist spécialisé" backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [ ] Outils en fin de phrase 2 : `grep -c "principalement en" backend/app/llm/prompts/cv/tailor_prompt.md` → ≥ 2 (consigne + exemple) ; `grep -c "Avec Python" backend/app/llm/prompts/cv/tailor_prompt.md` → 0
- [ ] Offre oncologie avec Bloc B : `cd backend && uv run python <scratchpad>/summary_eval.py 3 onco` → « total repris: 0 », « total ronflants: 0 » (noms d'employeur inclus), moyenne ≤ 70 mots
- [ ] Offre HCL (non-régression) : `cd backend && uv run python <scratchpad>/summary_eval.py 3 hcl` → mêmes seuils
- [ ] Type check: n/a — pas de type checker configuré pour le backend
- [ ] Manual check: les 6 accroches recopiées dans `## Notes` ; chacune suit les 3 temps (métier et types de travaux, outils et étendue, apport), reste générale (aucune entreprise ni mission détaillée) et chaque compétence citée se retrouve dans le profil (lecture par l'agent, puis validation par l'utilisateur)

## Steps
- [x] Step 1: Mettre à jour les deux tests de prompt de `test_cv_tailor.py` pour le nouveau contrat (70 mots, « Reste général », « N'emprunte à l'offre aucun terme », « avec une expérience dans », « principalement en », plus de « 45 mots » ni de consigne `critical` ni de « Scientist spécialisé » ni de « Avec Python ») ; les lancer, constater l'échec (RED).
- [x] Step 2: Réécrire la directive 3 de `tailor_prompt.md` : 3 phrases, 70 mots max ; 1) métier (titre du profil ou postes occupés) « avec une expérience dans » les domaines et grands types de travaux du parcours, 2) étendue de l'intervention puis outils principaux en fin de phrase (« principalement en … »), 3) apport aux équipes ; texte général ; l'offre choisit seulement quelles forces réelles passer en premier ; aucun terme de l'offre non prouvé ; « je » admis après la 1re phrase ; « spécialisé dans » reste interdit ; schéma JSON à 70 mots. Supprimer les phrases remplacées.
- [x] Step 3: Lancer la suite CV (tailor, guards, templates, pdf_renderer) ; tout vert.
- [x] Step 4: Lancer `summary_eval.py 3 onco` puis `summary_eval.py 3 hcl` ; vérifier les seuils ; recopier les accroches dans `## Notes`.
- [x] Step 5 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the replaced symbols. Confirm 0 orphans.

## Code Review
- Dead code removed: yes — phrases remplacées absentes de backend/app (seules occurrences : assertions « not in » des tests et phrases sans rapport dans les prompts de lettre)
- Build status: pass — import exit 0 ; pytest CV (tailor, guards, templates, pdf_renderer) 135 passed
- Type errors: none (pas de type checker configuré)
- Unintended side effects: none — `{target_company}` reste utilisé dans la section offre ; aucun code Python touché
- Security surface touched: no
- Verdict: ✅ DONE — avec dérogation utilisateur sur le seuil « total repris: 0 » de l’offre hcl (« indicateurs », 1 accroche sur 3) ; évals non relancées à la clôture (prompt inchangé depuis le dernier run, coût)

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-10T08:45Z | claude-code | baseline | import exit 0 ; pytest tailor+guards 13 passed ; consignes remplacées 3 ; interdiction d'emprunt 0 ; évals LLM en attente du feu vert
- 2026-10-10T08:45Z | claude-code | step 1 | started
- 2026-10-10T08:46Z | claude-code | step 1 | done | RED : `pytest -k grounds_summary` échoue sur `assert 'guident la première phrase' not in prompt` (test_cv_tailor.py:255)
- 2026-10-10T08:46Z | claude-code | step 2 | started
- 2026-10-10T08:47Z | claude-code | step 2 | done | `pytest -k grounds_summary` 1 passed ; consignes remplacées 0 ; « N'emprunte à l'offre aucun terme » 1 ; ancienne phrase employeur 0 ; `{target_company}` toujours utilisé 1 fois (section offre)
- 2026-10-10T08:47Z | claude-code | step 3 | started
- 2026-10-10T08:48Z | claude-code | step 3 | done | import exit 0 ; `pytest test_cv_tailor test_cv_guards test_cv_templates test_cv_pdf_renderer` 135 passed
- 2026-10-10T08:59Z | claude-code | replan | redirection utilisateur : accroche générale (modèle fourni, ≈ 70 mots, « je » admis) au lieu de « missions + type de structure » ; steps 1-3 remis à [ ] avec le nouveau contrat, la version « type de structure » est remplacée
- 2026-10-10T08:59Z | claude-code | step 1 | started
- 2026-10-10T09:00Z | claude-code | step 1 | done | RED : `pytest -k "sober_summary or grounds_summary"` 2 failed (`'45 mots' not in prompt` ; `'Reste général' in prompt`)
- 2026-10-10T09:00Z | claude-code | step 2 | started
- 2026-10-10T09:01Z | claude-code | step 2 | done | 2 tests de prompt passed ; consignes remplacées 0 ; « N'emprunte à l'offre aucun terme » 1 ; « type de structure » 0
- 2026-10-10T09:01Z | claude-code | step 3 | started
- 2026-10-10T09:02Z | claude-code | step 3 | done | import exit 0 ; `pytest test_cv_tailor test_cv_guards test_cv_templates test_cv_pdf_renderer` 135 passed
- 2026-10-10T09:08Z | claude-code | replan | précision utilisateur : « avec une expérience dans… » au lieu de « spécialisé dans » (qui reste interdit) ; steps 1-3 rouverts
- 2026-10-10T09:08Z | claude-code | step 1 | started
- 2026-10-10T09:08Z | claude-code | step 1 | done | RED : `pytest -k grounds_summary` échoue sur `'Scientist spécialisé' not in prompt` (test_cv_tailor.py:260)
- 2026-10-10T09:08Z | claude-code | step 2 | started
- 2026-10-10T09:09Z | claude-code | step 2 | done | 2 tests de prompt passed ; « avec une expérience dans » 2 ; « Scientist spécialisé » 0 ; consignes remplacées 0 ; « N'emprunte à l'offre aucun terme » 1
- 2026-10-10T09:09Z | claude-code | step 3 | started
- 2026-10-10T09:10Z | claude-code | step 3 | done | import exit 0 ; `pytest test_cv_tailor test_cv_guards test_cv_templates test_cv_pdf_renderer` 135 passed
- 2026-10-10T09:13Z | claude-code | replan | choix utilisateur : outils en fin de phrase 2 (« principalement en … ») au lieu de « Avec Python, SQL et PySpark, » ; steps 1-3 rouverts
- 2026-10-10T09:13Z | claude-code | step 1 | started
- 2026-10-10T09:14Z | claude-code | step 1 | done | RED : `pytest -k grounds_summary` échoue sur `'Avec Python' not in prompt` (test_cv_tailor.py:262)
- 2026-10-10T09:14Z | claude-code | step 2 | started
- 2026-10-10T09:15Z | claude-code | step 2 | done | 2 tests de prompt passed ; « principalement en » 2 ; « Avec Python » 0 ; « avec une expérience dans » 2 ; « Scientist spécialisé » 0 ; consignes remplacées 0 ; « N'emprunte à l'offre aucun terme » 1
- 2026-10-10T09:15Z | claude-code | step 3 | started
- 2026-10-10T09:15Z | claude-code | step 3 | done | import exit 0 ; `pytest test_cv_tailor test_cv_guards test_cv_templates test_cv_pdf_renderer` 135 passed
- 2026-10-10T09:19Z | claude-code | step 4 | started | feu vert utilisateur (AskUserQuestion : « Éval puis déploiement »)
- 2026-10-10T09:20Z | claude-code | step 4 | failed | run 1 : onco repris 0, hcl repris 0, moyennes 70.3/70.3 (compte \w+, 61-68 mots à l'espace) ; lecture contre le profil : « modélisation statistique » (hcl), « indicateurs » (hcl x2), « biologistes et cliniciens » (onco), absents du profil et non détectés par le script
- 2026-10-10T09:21Z | claude-code | step 4 | fix 1 | prompt : « doit se retrouver dans le profil » + « livrable ou public visé » ; test étendu (RED puis 2 passed) ; script : listes élargies (indicateur, clinicien, biologiste, statisti) ; onco repris 2 (« modélisation statistique »), hcl repris 1 (« indicateur »)
- 2026-10-10T09:22Z | claude-code | step 4 | fix 2 | prompt : accroche rédigée « à partir du seul profil », relecture avant réponse, « même si l'analyse cite une preuve » ; 2 tests passed ; onco repris 0 ronflants 0 moy 67.0 ; hcl repris 1 (« indicateur ») ronflants 0 moy 65.7
- 2026-10-10T09:23Z | claude-code | step 4 | blocked | hcl « total repris: 1 » après 2 tentatives — décision utilisateur
- 2026-10-10T09:26Z | claude-code | step 4 | done | dérogation utilisateur (AskUserQuestion « Accepter et déployer ») sur l'emprunt résiduel « indicateurs » (hcl 1/3) ; dernier run : onco repris 0 ronflants 0 moy 67.0, hcl repris 1 ronflants 0 moy 65.7
- 2026-10-10T09:26Z | claude-code | step 5 | started
- 2026-10-10T09:27Z | claude-code | step 5 | done | 0 orphelin (scan des phrases remplacées dans backend/app, backend/tests, frontend/src)
- 2026-10-10T09:27Z | claude-code | close | done | DoD : import exit 0 ; 135 passed ; consignes remplacées 0 ; emprunt 1 ; « avec une expérience dans » 2 ; « Scientist spécialisé » 0 ; « principalement en » 2 ; « Avec Python » 0 ; évals = run 09:22Z (onco 0 repris, hcl 1 repris accepté par l'utilisateur)

## Notes
- Conventions lues : CLAUDE.md (= AGENTS.md = GEMINI.md), .cursorrules (lues au plan précédent, inchangées).
- `summary_eval.py` (scratchpad, hors dépôt) : offre `onco` fictive « Ingénieur IA - Oncologie de précision » avec une analyse Bloc B généreuse (IA appliquée à l'oncologie et modélisation statistique en `partial_match` critical, multi-omique et incertitude manquants), offre `hcl` reprise du plan précédent. Compte la longueur, les termes ronflants et noms d'employeur, et les termes de l'offre absents du profil. Mis à jour pour la nouvelle forme : « valorisation » retiré des termes ronflants (présent dans le modèle de l'utilisateur) ; « spécialisé » y reste, l'utilisateur n'en veut pas.
- Première version (08:45-08:48, remplacée) : 1re phrase = métier + type de structure, puis 2-3 missions réelles. Exemples écrits à la main montrés à l'utilisateur ; il a demandé à la place un texte plus général.
- Le run d'éval avec Bloc B a été refusé une première fois par le classifieur d'auto mode (« Production Reads ») alors qu'il ne lit que le profil de test local et appelle Gemini : feu vert utilisateur nécessaire pour l'étape 4.
- Prochaine action : avec le feu vert de l'utilisateur, lancer depuis `backend/` `uv run python <scratchpad>/summary_eval.py 3 onco` puis `… 3 hcl` (étape 4), puis teardown et close out.
- **Blocage étape 4 (09:23Z)** : après 2 tentatives de correction, `summary_eval.py 3 hcl` sort « total repris: 1 » (seuil 0) ; `3 onco` passe (0 repris, 0 ronflant, 67.0 mots). L'emprunt restant est « indicateurs » (offre HCL : « construisez des indicateurs »), 1 accroche sur 3. Le compte de mots du script (`\w+`) sépare les élisions (« l'extraction » = 2) : à l'espace, les accroches font 54 à 64 mots. « aide à la décision » est absent du profil mais vient de l'exemple de forme demandé par l'utilisateur.
- Correctifs appliqués pendant l'étape 4 (dans le périmètre) : directive 3 de `tailor_prompt.md`, une ligne ajoutée (« Rédige l'accroche à partir du seul profil candidat : chaque domaine, type de travaux, outil et public cité doit se retrouver dans le profil. Avant de répondre, relis l'accroche et retire tout terme absent du profil, même s'il figure dans l'offre ou dans l'analyse Bloc B. ») et la règle d'emprunt élargie (« livrable ou public visé », « même si l'analyse cite une preuve ») ; `test_load_tailor_prompt_grounds_summary_in_profile_experiences` vérifie ces deux ajouts.
- Accroches du dernier run (onco) :
  1. « Ingénieur Data et IA avec une expérience dans la santé, la recherche oncologique et l'ingénierie des données. J'interviens de l'automatisation des flux de données jusqu'au développement de modèles et d'applications d'IA, principalement en Python, SQL et NoSQL. Mon travail vise à fiabiliser les processus et apporter une aide à la décision aux équipes métier. »
  2. « Ingénieur Data & IA avec une expérience dans le traitement de données de santé, le machine learning et l'automatisation de flux. J'interviens de l'extraction et l'intégration des données jusqu'au déploiement de modèles et d'applications d'IA, principalement en Python, SQL et environnements cloud. Mon objectif est de fiabiliser les flux de données et d'outiller l'aide à la décision pour les équipes métiers. »
  3. « Ingénieur Data & IA avec une expérience dans l'ingénierie des données, le traitement du langage naturel et le déploiement de modèles d'intelligence artificielle en santé. J'interviens de l'extraction et l'intégration des données jusqu'à la mise en production d'outils d'aide à la décision, principalement en Python et SQL. Mon travail vise à automatiser les flux documentaires et fiabiliser l'accès aux informations pour les équipes métiers. »
- Accroches du dernier run (hcl) :
  1. « Data Scientist avec une expérience dans le traitement des données de santé, les pipelines de données et le traitement du langage naturel. J'interviens de l'extraction et la conciliation des données hétérogènes jusqu'à la restitution via des modèles et des tableaux de bord, principalement en Python et SQL. Mon travail apporte aux équipes médicales et de recherche des flux fiabilisés pour l'exploitation de leurs données. »
  2. « Data Scientist avec une expérience dans le traitement des données de santé, la modélisation et l'ingénierie des flux de données. J'interviens de l'extraction et l'intégration de sources hétérogènes jusqu'au déploiement d'indicateurs et d'outils analytiques, principalement en Python et SQL. Mon travail apporte aux équipes médicales et de recherche des données fiabilisées pour éclairer leurs décisions cliniques. » ← « indicateurs »
  3. « Data Scientist avec une expérience dans le secteur de la santé, le traitement de données cliniques et la mise en place de pipelines de données. J'interviens de l'extraction et l'intégration de sources hétérogènes jusqu'au déploiement de modèles et de tableaux de bord, principalement en Python et SQL. Mon travail permet de fiabiliser les flux de données pour les équipes médicales et métiers. »
- Décision utilisateur (2026-10-10T09:27Z) : emprunt résiduel « indicateurs » accepté ; commit, push et déploiement demandés.
